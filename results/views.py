from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.db.models import Count, Avg, Q
from django.utils import timezone
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator

from .models import ExamResult, ExamViolation
from classroom.models import Exam, Classroom
from monitoring.models import Alert, ExamSession, StreamFrame
from Users.models import User

import json
from datetime import timedelta

@login_required
def teacher_results_dashboard(request):
    """Dashboard view for teachers to see all exam results and flagged exams"""
    # Check if user is a teacher
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
    
    # Get all exams created by this teacher
    exams = Exam.objects.filter(teacher=request.user).order_by('-created_at')
    
    # Get counts of results by status for each exam
    exam_data = []
    for exam in exams:
        results_count = ExamResult.objects.filter(exam=exam).count()
        flagged_count = ExamResult.objects.filter(exam=exam, is_flagged=True, is_reviewed=False).count()
        reviewed_count = ExamResult.objects.filter(exam=exam, is_reviewed=True).count()
        penalty_count = ExamResult.objects.filter(exam=exam, status='penalty_applied').count()
        
        avg_score = ExamResult.objects.filter(exam=exam).aggregate(avg_score=Avg('score'))['avg_score'] or 0
        
        exam_data.append({
            'exam': exam,
            'results_count': results_count,
            'flagged_count': flagged_count,
            'reviewed_count': reviewed_count,
            'penalty_count': penalty_count,
            'avg_score': round(avg_score, 2),
        })
    
    # Get recent flagged exams
    recent_flagged = ExamResult.objects.filter(
        exam__teacher=request.user, 
        is_flagged=True,
        is_reviewed=False
    ).order_by('-created_at')[:5]
    
    context = {
        'exam_data': exam_data,
        'recent_flagged': recent_flagged,
    }
    
    return render(request, 'results/teacher_dashboard.html', context)

@login_required
def exam_results_list(request, exam_id):
    """View for teachers to see all results for a specific exam"""
    # Check if user is a teacher
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
    
    exam = get_object_or_404(Exam, id=exam_id, teacher=request.user)
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort_by', '-completion_time')  # Default sort by completion time
    
    # Filter results
    results = ExamResult.objects.filter(exam=exam)
    
    if status_filter:
        if status_filter == 'flagged':
            results = results.filter(is_flagged=True, is_reviewed=False)
        elif status_filter == 'reviewed':
            results = results.filter(is_reviewed=True)
        elif status_filter in dict(ExamResult.RESULT_STATUS):
            results = results.filter(status=status_filter)
    
    if search_query:
        results = results.filter(
            Q(student__username__icontains=search_query) | 
            Q(student__first_name__icontains=search_query) | 
            Q(student__last_name__icontains=search_query)
        )
    
    # Sort results
    results = results.order_by(sort_by)
    
    # Paginate results
    paginator = Paginator(results, 20)  # 20 results per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'exam': exam,
        'results_page': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
        'sort_by': sort_by,
        'status_choices': ExamResult.RESULT_STATUS,
        'total_results': results.count(),
        'flagged_count': results.filter(is_flagged=True, is_reviewed=False).count(),
        'avg_score': results.aggregate(avg=Avg('score'))['avg'] or 0,
    }
    
    return render(request, 'results/exam_results_list.html', context)

@login_required
def review_flagged_exam(request, result_id):
    """View for teachers to review a flagged exam and its alerts"""
    # Check if user is a teacher
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
    
    # Get the exam result
    result = get_object_or_404(ExamResult, id=result_id)
    
    # Ensure this teacher owns the exam
    if result.exam.teacher != request.user:
        return HttpResponseForbidden("You don't have permission to review this exam")
    
    # Get the exam session and alerts
    try:
        session = ExamSession.objects.get(student=result.student, exam=result.exam)
        alerts = Alert.objects.filter(session=session).order_by('timestamp')
        
        # Get frames for evidence
        frames = StreamFrame.objects.filter(session=session).order_by('timestamp')
    except ExamSession.DoesNotExist:
        session = None
        alerts = []
        frames = []
    
    # Get violations if already reviewed
    violations = ExamViolation.objects.filter(exam_result=result).order_by('timestamp')
    
    context = {
        'result': result,
        'session': session,
        'alerts': alerts,
        'frames': frames,
        'violations': violations,
        'violation_types': ExamViolation.VIOLATION_TYPES,
        'severity_levels': ExamViolation.SEVERITY_LEVELS,
    }
    
    return render(request, 'results/review_flagged_exam.html', context)

@require_POST
@login_required
def process_review(request, result_id):
    """Process a teacher's review of a flagged exam"""
    # Check if user is a teacher
    if request.user.user_type != 'teacher':
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    # Get the exam result
    result = get_object_or_404(ExamResult, id=result_id)
    
    # Ensure this teacher owns the exam
    if result.exam.teacher != request.user:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    # Get form data
    try:
        data = json.loads(request.body)
        action = data.get('action', '')
        notes = data.get('notes', '')
        violations = data.get('violations', [])
        
        if action == 'clear':
            # Mark as reviewed with no violations
            result.mark_as_reviewed(notes=notes)
            message = 'Exam cleared and marked as reviewed'
            
        elif action == 'confirm_violations':
            # Calculate total penalty
            total_penalty = 0
            
            # Process each violation
            for violation_data in violations:
                violation_type = violation_data.get('type')
                severity = violation_data.get('severity')
                description = violation_data.get('description')
                penalty = float(violation_data.get('penalty', 0))
                alert_id = violation_data.get('alert_id')
                
                # Create violation record
                violation = ExamViolation(
                    exam_result=result,
                    violation_type=violation_type,
                    severity=severity,
                    description=description,
                    penalty_applied=penalty,
                    reviewed_by=request.user
                )
                
                # Link to alert if provided
                if alert_id:
                    try:
                        alert = Alert.objects.get(id=alert_id)
                        violation.alert = alert
                        
                        # Use alert screenshot if available
                        if alert.screenshot:
                            violation.evidence_screenshot = alert.screenshot
                    except Alert.DoesNotExist:
                        pass
                
                violation.save()
                total_penalty += penalty
            
            # Apply the penalty to the result
            if total_penalty > 0:
                result.apply_penalty(total_penalty, notes=notes)
            else:
                result.mark_as_reviewed(notes=notes)
            
            message = f'Exam reviewed with {len(violations)} violations confirmed'
        
        else:
            return JsonResponse({'success': False, 'error': 'Invalid action'}, status=400)
        
        # Include the exam ID in the response for redirect
        return JsonResponse({
            'success': True, 
            'message': message,
            'exam_id': result.exam.id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def student_results(request):
    """View for students to see their own exam results"""
    # Check if user is a student
    if request.user.user_type != 'student':
        return redirect('Users:access_denied')
    
    # Get all results for this student
    results = ExamResult.objects.filter(student=request.user).order_by('-completion_time')
    
    context = {
        'results': results,
    }
    
    return render(request, 'results/student_results.html', context)

@login_required
def view_result_detail(request, result_id):
    """View for detailed result information"""
    # Get the result
    result = get_object_or_404(ExamResult, id=result_id)
    
    # Check permissions - either the student who took the exam or the teacher who created it
    if request.user != result.student and request.user != result.exam.teacher:
        return redirect('Users:access_denied')
    
    # Get questions and responses
    questions = result.exam.questions.all()
    responses = result.responses
    
    # Create a list of questions with student's answers and correct answers
    question_data = []
    for question in questions:
        student_answer = responses.get(str(question.id), None)
        is_correct = str(student_answer) == str(question.correct_option) if student_answer else False
        
        question_data.append({
            'question': question,
            'student_answer': student_answer,
            'is_correct': is_correct,
            'correct_option': question.correct_option,
        })
    
    # Get violations if teacher or if student and result is not flagged/under review
    violations = []
    if request.user.user_type == 'teacher' or (request.user.user_type == 'student' and result.is_reviewed):
        violations = ExamViolation.objects.filter(exam_result=result)
    
    context = {
        'result': result,
        'question_data': question_data,
        'violations': violations,
        'is_teacher': request.user.user_type == 'teacher',
    }
    
    return render(request, 'results/result_detail.html', context)

@login_required
def generate_exam_report(request, exam_id):
    """Generate comprehensive report for an exam"""
    # Check if user is a teacher
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
    
    exam = get_object_or_404(Exam, id=exam_id, teacher=request.user)
    results = ExamResult.objects.filter(exam=exam)
    
    # Get summary statistics
    total_students = results.count()
    avg_score = results.aggregate(avg=Avg('score'))['avg'] or 0
    passing_count = results.filter(status='passed').count()
    failing_count = results.filter(status='failed').count()
    flagged_count = results.filter(is_flagged=True).count()
    penalized_count = results.filter(status='penalty_applied').count()
    
    # Get alert statistics
    sessions = ExamSession.objects.filter(exam=exam)
    alerts_by_type = Alert.objects.filter(session__in=sessions).values('alert_type').annotate(count=Count('id'))
    
    # Format alert types for display
    alert_stats = []
    for alert_data in alerts_by_type:
        alert_type = alert_data['alert_type']
        count = alert_data['count']
        
        # Find display name based on choices in Alert model
        display_name = next((name for code, name in Alert.ALERT_TYPES if code == alert_type), alert_type)
        
        alert_stats.append({
            'type': display_name,
            'count': count,
        })
    
    context = {
        'exam': exam,
        'total_students': total_students,
        'avg_score': round(avg_score, 2),
        'passing_count': passing_count,
        'failing_count': failing_count,
        'passing_percentage': round(passing_count / total_students * 100, 2) if total_students > 0 else 0,
        'flagged_count': flagged_count,
        'penalized_count': penalized_count,
        'alert_stats': alert_stats,
        'results': results,
    }
    
    return render(request, 'results/exam_report.html', context)

@login_required
def review_frames(request, result_id):
    """AJAX endpoint to fetch more monitoring frames for a result"""
    # Check if user is a teacher
    if request.user.user_type != 'teacher':
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    # Get the exam result
    result = get_object_or_404(ExamResult, id=result_id)
    
    # Ensure this teacher owns the exam
    if result.exam.teacher != request.user:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    # Get page number from request
    page = int(request.GET.get('page', 1))
    frames_per_page = 20
    
    # Calculate offset
    offset = (page - 1) * frames_per_page
    
    # Get session and frames
    try:
        session = ExamSession.objects.get(student=result.student, exam=result.exam)
        frames = StreamFrame.objects.filter(session=session).order_by('timestamp')[offset:offset + frames_per_page]
        
        # Check if there are more frames
        total_frames = StreamFrame.objects.filter(session=session).count()
        has_more = (offset + frames_per_page) < total_frames
        
        # Format frame data
        frame_data = []
        for frame in frames:
            frame_data.append({
                'frame_path': frame.frame_path,
                'timestamp': frame.timestamp.strftime('%H:%M:%S'),
                'id': frame.id
            })
        
        return JsonResponse({
            'success': True,
            'frames': frame_data,
            'has_more': has_more
        })
        
    except ExamSession.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'error': 'No exam session found', 
            'frames': [],
            'has_more': False
        })
