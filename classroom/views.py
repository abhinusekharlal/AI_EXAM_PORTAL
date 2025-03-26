from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from Users.models import User
from .models import Classroom, Exam, Question
from django.contrib.auth.decorators import login_required
from .forms import ClassroomForm, QuestionForm, ExamForm
from django import forms
from django.utils import timezone
from datetime import timedelta, datetime
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
import json
# Import the ExamSession model
from monitoring.models import ExamSession
# Import the ExamResult model
from results.models import ExamResult

import threading

from django.http import StreamingHttpResponse
import cv2

class JoinClassForm(forms.Form):
    class_code = forms.CharField(max_length=10, label='Class Code')

# Create your views here.

@login_required
def create_class(request):
    if request.method == 'POST':
        form = ClassroomForm(request.POST)
        if form.is_valid():
            new_class = form.save(commit=False)
            new_class.teacher = request.user
            new_class.save()
            return redirect('Users:dashboard', username=request.user.username)
    else:
        form = ClassroomForm()
    return render(request, 'classroom/create_class.html', {'form': form})

@login_required
def join_class(request):
    if request.method == 'POST':
        form = JoinClassForm(request.POST)
        if form.is_valid():
            class_code = form.cleaned_data['class_code']
            try:
                classroom = Classroom.objects.get(class_code=class_code)
                classroom.students.add(request.user)
                return redirect('Users:dashboard', username=request.user.username)
            except Classroom.DoesNotExist:
                return render(request, 'classroom/join_class.html', {'form': form, 'error': 'Class does not exist'})
    else:
        form = JoinClassForm()
    return render(request, 'classroom/join_class.html', {'form': form})

@login_required
def delete_class(request, class_id):
    classroom = get_object_or_404(Classroom, id=class_id, teacher=request.user)
    if request.method == 'POST':
        classroom.delete()
        return redirect('Users:dashboard', username=request.user.username)

@login_required
def manage_students(request, class_id):
    classroom = get_object_or_404(Classroom, id=class_id, teacher=request.user)
    joined_students = classroom.students.all()
    context = {
        'classroom': classroom,
        'joined_students': joined_students,
    }
    return render(request, 'classroom/manage_students.html', context)

@login_required
def remove_student(request, class_id, student_id):
    classroom = get_object_or_404(Classroom, id=class_id, teacher=request.user)
    student = get_object_or_404(User, id=student_id)
    classroom.students.remove(student)
    return redirect('classroom:manage_students', class_id=class_id)

@login_required
def view_texams(request):
    """
    Display all exams created by the teacher with proper filtering and sorting
    """
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
    
    # Get all exams created by this teacher
    exams = Exam.objects.filter(teacher=request.user)
    
    # Get filter parameters from request
    status_filter = request.GET.get('status', '')
    class_filter = request.GET.get('class', '')
    date_filter = request.GET.get('date', '')
    
    # Apply filters if provided
    if status_filter:
        exams = exams.filter(status=status_filter)
    
    if class_filter:
        exams = exams.filter(exam_class__id=class_filter)
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            exams = exams.filter(exam_date=filter_date)
        except ValueError:
            # Invalid date format, ignore this filter
            pass
    
    # Sort exams by date (descending) and time
    exams = exams.order_by('-exam_date', 'exam_time')
    
    # Get classes for filter dropdown
    teacher_classes = Classroom.objects.filter(teacher=request.user)
    
    # Count exams by status for summary
    draft_count = exams.filter(status='draft').count()
    published_count = exams.filter(status='published').count()
    completed_count = exams.filter(status='completed').count()
    
    # Check if any exams are happening today
    today = timezone.now().date()
    today_exams = exams.filter(exam_date=today).count()
    
    context = {
        'exams': exams,
        'teacher_classes': teacher_classes,
        'draft_count': draft_count,
        'published_count': published_count, 
        'completed_count': completed_count,
        'today_exams': today_exams,
        'status_filter': status_filter,
        'class_filter': class_filter,
        'date_filter': date_filter,
    }
    
    return render(request, 'classroom/Exam_Schedule.html', context)

@login_required
def add_exam(request):
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
    
    if request.method == 'POST':
        exam_form = ExamForm(request.POST, request=request)
        questions_data = []
        
        # Collect all question forms data
        i = 0
        while f'question_{i}-question_text' in request.POST:
            question_data = {
                'question_text': request.POST.get(f'question_{i}-question_text'),
                'option1': request.POST.get(f'question_{i}-option1'),
                'option2': request.POST.get(f'question_{i}-option2'),
                'option3': request.POST.get(f'question_{i}-option3'),
                'option4': request.POST.get(f'question_{i}-option4'),
                'correct_option': request.POST.get(f'question_{i}-correct_option'),
            }
            questions_data.append(question_data)
            i += 1

        if exam_form.is_valid():
            exam = exam_form.save(commit=False)
            exam.teacher = request.user
            # Use the status from the form instead of hardcoding to published
            exam.status = exam_form.cleaned_data.get('status', 'draft')
            # Visibility to students is handled by the form field directly
            exam.save()

            # Save all questions
            for question_data in questions_data:
                question_form = QuestionForm(question_data)
                if question_form.is_valid():
                    question = question_form.save(commit=False)
                    question.exam = exam
                    question.save()

            return redirect('classroom:schedule')
    else:
        exam_form = ExamForm(request=request)
    
    return render(request, 'classroom/create_exam.html', {
        'exam_form': exam_form
    })

@login_required
def add_question_form(request):
    """View to return a new question form via HTMX"""
    try:
        question_count = int(request.GET.get('count', 0))
    except ValueError:
        question_count = 0
        
    form = QuestionForm(prefix=f'question_{question_count}')
    context = {
        'form': form,
        'number': question_count + 1,
        'prefix': f'question_{question_count}'
    }
    
    print(f"Adding question form {question_count + 1}")  # Debug print
    return render(request, 'classroom/partials/question_form.html', context)

@login_required
def delete_question(request):
    """Handle question deletion via HTMX"""
    if request.method == 'DELETE':
        # Since we're just removing the form element, no need to actually delete from DB
        # Just return a successful response
        return HttpResponse(status=200)
    elif request.method == 'POST':
        # Allow POST as a fallback method for HTMX
        return HttpResponse(status=200)
    return HttpResponseBadRequest()

def delete_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if request.method == 'POST':
        exam.delete()
        return redirect('classroom:schedule')

@login_required
def edit_exam(request, exam_id):
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
    
    exam = get_object_or_404(Exam, id=exam_id)
    questions = Question.objects.filter(exam=exam).order_by('id')
    
    if request.method == 'POST':
        exam_form = ExamForm(request.POST, instance=exam, request=request)
        questions_data = []
        question_ids = []
        
        # Collect all question forms data and IDs
        i = 0
        while f'question_{i}-question_text' in request.POST:
            question_id = request.POST.get(f'question_{i}-id', None)
            question_data = {
                'question_text': request.POST.get(f'question_{i}-question_text'),
                'option1': request.POST.get(f'question_{i}-option1'),
                'option2': request.POST.get(f'question_{i}-option2'),
                'option3': request.POST.get(f'question_{i}-option3'),
                'option4': request.POST.get(f'question_{i}-option4'),
                'correct_option': request.POST.get(f'question_{i}-correct_option'),
            }
            questions_data.append((question_id, question_data))
            if question_id:
                question_ids.append(int(question_id))
            i += 1

        if exam_form.is_valid():
            # Save exam data
            exam = exam_form.save(commit=False)
            exam.teacher = request.user
            exam.status = exam_form.cleaned_data.get('status', 'draft')
            exam.save()
            
            # Delete questions that were removed from the form
            questions.exclude(id__in=question_ids).delete()
            
            # Update or create questions
            for question_id, question_data in questions_data:
                question_form = QuestionForm(question_data)
                if question_form.is_valid():
                    if question_id:
                        # Update existing question
                        try:
                            question = Question.objects.get(id=question_id, exam=exam)
                            for key, value in question_data.items():
                                setattr(question, key, value)
                            question.save()
                        except Question.DoesNotExist:
                            # If the question ID doesn't exist, create a new one
                            question = question_form.save(commit=False)
                            question.exam = exam
                            question.save()
                    else:
                        # Create new question
                        question = question_form.save(commit=False)
                        question.exam = exam
                        question.save()
            
            return redirect('classroom:schedule')
    else:
        exam_form = ExamForm(instance=exam, request=request)
    
    return render(request, 'classroom/edit_exam.html', {
        'exam_form': exam_form,
        'exam': exam
    })

@login_required
def view_exam(request, exam_id):
    if request.user.user_type != 'student':
        return redirect('Users:access_denied')
    
    exam = get_object_or_404(Exam, id=exam_id)
    
    # Check if the exam is visible to students
    current_datetime = timezone.now()
    exam_start_datetime = datetime.combine(exam.exam_date, exam.exam_time)
    exam_start_datetime = timezone.make_aware(exam_start_datetime)
    
    # If exam is not published, or not visible and hasn't started yet, redirect
    if exam.status != 'published' or (not exam.visibility_to_students and current_datetime < exam_start_datetime):
        return redirect('Users:dashboard', username=request.user.username)
    
    questions = Question.objects.filter(exam=exam).order_by('id')
    
    # Use the duration property which calculates from start and end time
    duration_minutes = int(exam.duration.total_seconds() / 60)
    
    # Get current time using Django's timezone
    current_time = timezone.now()
    
    context = {
        'exam': exam,
        'questions': questions,
        'duration_minutes': duration_minutes,
        'total_questions': questions.count(),
        'csrf_token': request.COOKIES.get('csrftoken'),
        'start_time': current_time.isoformat(),
    }
    
    # Set exam session data in Django session
    request.session[f'exam_{exam_id}_started'] = True
    request.session[f'exam_{exam_id}_start_time'] = current_time.isoformat()
    
    # Create or get an ExamSession record for monitoring
    exam_session, created = ExamSession.objects.get_or_create(
        exam=exam,
        student=request.user,
        is_active=True,
        defaults={
            'started_at': current_time,
            'last_activity': current_time
        }
    )
    
    return render(request, 'classroom/exam_interface.html', context)

@login_required
def submit_exam(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            exam_id = data.get('examId')
            answers = data.get('answers', {})
            
            if not exam_id:
                return JsonResponse({'success': False, 'error': 'Missing exam ID'}, status=400)
            
            exam = get_object_or_404(Exam, id=exam_id)
            
            # Try to get the start time from session
            start_time_str = request.session.get(f'exam_{exam_id}_start_time')
            start_time = None
            if start_time_str:
                try:
                    start_time = datetime.fromisoformat(start_time_str)
                except (ValueError, TypeError):
                    pass
            
            # Get or mark inactive the exam session
            try:
                exam_session = ExamSession.objects.get(
                    exam_id=exam_id,
                    student=request.user,
                    is_active=True
                )
                exam_session.is_active = False
                exam_session.save()
                
                # Use the session start time if available
                if not start_time and exam_session.started_at:
                    start_time = exam_session.started_at
                    
            except ExamSession.DoesNotExist:
                pass  # No active session found, which is unexpected but we can continue
            
            # Create permanent exam result record
            exam_result = ExamResult.create_from_submission(
                student=request.user,
                exam=exam,
                answers=answers,
                start_time=start_time
            )
            
            # Store the result ID and score in the session for the completion page
            request.session[f'exam_{exam_id}_result_id'] = str(exam_result.id)
            request.session[f'exam_{exam_id}_score'] = exam_result.score
            
            return JsonResponse({
                'success': True,
                'score': exam_result.score,
                'redirect_url': reverse('classroom:exam_completed')
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)


@login_required
def exam_completed(request):
    try:
        # First try to get the result directly if we have the ID
        result_id = None
        exam_id = None
        
        # Find the most recent exam result ID from the session
        for key in request.session.keys():
            if key.endswith('_result_id'):
                exam_id = key.split('_')[1]
                result_id = request.session.get(key)
                # Clear the session key after retrieving it
                del request.session[key]
                break
        
        if result_id:
            try:
                # Get the stored result and ensure it belongs to this student
                exam_result = ExamResult.objects.select_related('exam').get(
                    id=result_id, 
                    student=request.user
                )
                
                context = {
                    'exam': exam_result.exam,
                    'score': exam_result.score,
                    'completion_time': exam_result.completion_time,
                    'correct_answers': exam_result.correct_answers,
                    'total_questions': exam_result.total_questions,
                    'duration': exam_result.duration_in_minutes,
                    'status': exam_result.status,
                    'result': exam_result,
                }
                
                return render(request, 'classroom/exam_completed.html', context)
                
            except ExamResult.DoesNotExist:
                pass

        # Fallback to the most recent completed exam session
        last_exam_session = ExamSession.objects.filter(
            student=request.user,
            is_active=False
        ).select_related('exam').order_by('-last_activity').first()
        
        if last_exam_session:
            exam = last_exam_session.exam
            
            # Try to find a result for this exam
            try:
                exam_result = ExamResult.objects.get(
                    student=request.user, 
                    exam=exam
                )
                
                context = {
                    'exam': exam_result.exam,
                    'score': exam_result.score,
                    'completion_time': exam_result.completion_time,
                    'correct_answers': exam_result.correct_answers,
                    'total_questions': exam_result.total_questions,
                    'duration': exam_result.duration_in_minutes,
                    'status': exam_result.status,
                    'result': exam_result,
                }
                
                return render(request, 'classroom/exam_completed.html', context)
                
            except ExamResult.DoesNotExist:
                # If no result exists, use session data
                score = request.session.get(f'exam_{exam.id}_score', 0)
                completion_time = last_exam_session.last_activity
                
                context = {
                    'exam': exam,
                    'score': score,
                    'completion_time': completion_time
                }
                
                return render(request, 'classroom/exam_completed.html', context)
                
    except Exception as e:
        # Log the exception
        print(f"Error in exam_completed view: {str(e)}")
    
    # If we get here, either there's no completed exam or an error occurred
    return render(request, 'classroom/exam_completed.html', {
        'generic_completion': True
    })


@login_required
def exam_results(request, exam_id):
    """
    Display results for a specific exam
    """
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
    
    # Get the exam and verify ownership
    exam = get_object_or_404(Exam, id=exam_id, teacher=request.user)
    
    # Get all results for this exam
    from results.models import ExamResult
    results = ExamResult.objects.filter(exam=exam).select_related('student')
    
    # Calculate summary statistics
    total_students = results.count()
    if total_students > 0:
        avg_score = sum(result.score for result in results) / total_students
        passed_students = results.filter(status='passed').count()
        pass_rate = (passed_students / total_students) * 100 if total_students > 0 else 0
    else:
        avg_score = 0
        passed_students = 0
        pass_rate = 0
    
    # Get class information
    classroom = exam.exam_class
    enrolled_students = classroom.students.count() if classroom else 0
    completion_rate = (total_students / enrolled_students) * 100 if enrolled_students > 0 else 0
    
    context = {
        'exam': exam,
        'results': results,
        'total_students': total_students,
        'avg_score': round(avg_score, 2),
        'pass_rate': round(pass_rate, 2),
        'passed_students': passed_students,
        'enrolled_students': enrolled_students,
        'completion_rate': round(completion_rate, 2),
    }
    
    return render(request, 'classroom/exam_results.html', context)

