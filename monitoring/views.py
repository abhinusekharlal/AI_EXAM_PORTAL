from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone
from classroom.models import Exam, Question
from Users.models import User
from Users.middleware import UserSession
from monitoring.models import ExamSession, Alert, StreamFrame
from .frame_processor import FrameProcessor
import datetime
import json
import base64
import os
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
import uuid
from django.conf import settings

# Create your views here.

@login_required
def monitoring_dashboard(request):
    """
    Display the monitoring dashboard with active exams, student sessions, and alerts
    """
    # Check if user is a teacher
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
        
    # Get active exams created by this teacher (exams today or in the future)
    now = timezone.now()
    today = now.date()
    
    active_exams = Exam.objects.filter(
        teacher=request.user,
        exam_date__gte=today
    ).order_by('exam_date', 'exam_time')
    
    # Get active exam sessions for exams taught by this teacher
    active_sessions = ExamSession.objects.filter(
        exam__in=active_exams,
        is_active=True
    ).select_related('student', 'exam').order_by('-started_at')
    
    # Get recent alerts for active sessions
    recent_alerts = Alert.objects.filter(
        session__in=active_sessions,
        is_reviewed=False
    ).select_related('session', 'session__student', 'session__exam').order_by('-timestamp')[:20]
    
    context = {
        'active_exams': active_exams,
        'active_sessions': active_sessions,
        'recent_alerts': recent_alerts
    }
    
    return render(request, 'monitoring/monitoring_dashboard.html', context)

@login_required
def exam_monitor(request, exam_id):
    """
    Display live monitoring interface for a specific exam
    """
    # Check if user is a teacher
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
        
    # Get exam object and verify ownership
    exam = get_object_or_404(Exam, id=exam_id)
    if exam.teacher != request.user:
        return redirect('Users:access_denied')
    
    # Check for specific student filter in query parameters
    student_filter = request.GET.get('student')
    
    # Get active sessions for this exam
    active_sessions = ExamSession.objects.filter(
        exam=exam,
        is_active=True
    ).select_related('student').order_by('-started_at')
    
    # Get active alerts for this exam's sessions
    active_alerts = Alert.objects.filter(
        session__exam=exam,
        is_reviewed=False
    ).select_related('session', 'session__student').order_by('-timestamp')
    
    context = {
        'exam': exam,
        'active_sessions': active_sessions,
        'active_alerts': active_alerts,
        'student_filter': student_filter
    }
    
    return render(request, 'monitoring/exam_monitor.html', context)

@login_required
def monitoring_student(request, exam_id, student_id):
    """
    Display detailed monitoring for a single student in an exam
    """
    # Check if user is a teacher
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
        
    # Get exam object and verify ownership
    exam = get_object_or_404(Exam, id=exam_id)
    if exam.teacher != request.user:
        return redirect('Users:access_denied')
    
    # Get student object
    student = get_object_or_404(User, id=student_id)
    
    # Get active session for this student and exam
    try:
        session = ExamSession.objects.get(
            exam=exam,
            student=student,
            is_active=True
        )
    except ExamSession.DoesNotExist:
        return redirect('monitoring:exam_monitor', exam_id=exam_id)
    
    # Get alerts for this session
    alerts = Alert.objects.filter(session=session).order_by('-timestamp')
    
    context = {
        'exam': exam,
        'student': student,
        'session': session,
        'alerts': alerts
    }
    
    return render(request, 'monitoring/monitoring_student.html', context)

@login_required
def mark_alert_reviewed(request, alert_id):
    """
    Mark an alert as reviewed
    """
    # Check if user is a teacher
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
    
    alert = get_object_or_404(Alert, id=alert_id)
    
    # Verify that this alert belongs to an exam that the teacher owns
    if alert.session.exam.teacher != request.user:
        return redirect('Users:access_denied')
    
    alert.is_reviewed = True
    alert.reviewed_at = timezone.now()
    alert.reviewed_by = request.user
    alert.save()
    
    return redirect(request.META.get('HTTP_REFERER', 'monitoring:examdashboard'))

@login_required
@csrf_protect
@require_POST
def upload_frame(request):
    """Handle webcam frame uploads from exam interface"""
    try:
        data = json.loads(request.body)
        exam_id = data.get('exam_id')
        image_data = data.get('image_data')
        
        if not exam_id or not image_data:
            return JsonResponse({'success': False, 'message': 'Missing required data'}, status=400)
        
        # Get exam session
        try:
            session = ExamSession.objects.get(
                exam_id=exam_id,
                student=request.user,
                is_active=True
            )
        except ExamSession.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'No active exam session'}, status=404)
        
        # Process image data
        if image_data.startswith('data:image'):
            # Extract base64 data
            format, imgstr = image_data.split(';base64,')
            ext = format.split('/')[-1]
            
            # Generate unique filename
            filename = f"frame_{session.id}_{uuid.uuid4().hex}.{ext}"
            filepath = os.path.join('monitoring_frames', filename)
            
            # Save image to storage
            from django.core.files.base import ContentFile
            from django.core.files.storage import default_storage
            
            image_data_binary = base64.b64decode(imgstr)
            saved_path = default_storage.save(filepath, ContentFile(image_data_binary))
            
            # Create stream frame record
            frame = StreamFrame.objects.create(
                session=session,
                frame_path=saved_path,
                timestamp=timezone.now()
            )
            
            # Process frame with YOLO and face detection
            processor = FrameProcessor(session)
            alerts = processor.process_frame(os.path.join(settings.MEDIA_ROOT, saved_path))
            
            # Update session last activity
            session.last_activity = timezone.now()
            session.save()
            
            # Return response with any alerts
            return JsonResponse({
                'success': True,
                'alerts': [{
                    'type': alert.alert_type,
                    'description': alert.description,
                    'severity': alert.severity,
                    'confidence': alert.confidence
                } for alert in alerts] if alerts else []
            })
            
        return JsonResponse({'success': False, 'message': 'Invalid image data'}, status=400)
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

# New API endpoints for exam monitoring interface

@login_required
def api_exam_sessions(request, exam_id):
    """API endpoint to get active sessions for an exam"""
    # Check if user is a teacher
    if request.user.user_type != 'teacher':
        return JsonResponse({'error': 'Access denied'}, status=403)
        
    # Get exam object and verify ownership
    exam = get_object_or_404(Exam, id=exam_id)
    if exam.teacher != request.user:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Get active sessions for this exam
    active_sessions = ExamSession.objects.filter(
        exam=exam,
        is_active=True
    ).select_related('student')
    
    # Format sessions for JSON response
    sessions_data = []
    for session in active_sessions:
        sessions_data.append({
            'id': session.id,
            'student_id': session.student.id,
            'student_name': session.student.get_full_name() or session.student.username,
            'started_at': session.started_at.isoformat(),
            'last_activity': session.last_activity.isoformat(),
            'is_active': session.is_active
        })
    
    # Get recent alerts
    recent_alerts = Alert.objects.filter(
        session__exam=exam,
        is_reviewed=False
    ).select_related('session', 'session__student').order_by('-timestamp')[:20]
    
    # Format alerts for JSON response
    alerts_data = []
    for alert in recent_alerts:
        alerts_data.append({
            'id': alert.id,
            'session_id': alert.session.id,
            'student_id': alert.session.student.id,
            'student_name': alert.session.student.get_full_name() or alert.session.student.username,
            'alert_type': alert.alert_type,
            'description': alert.description,
            'severity': alert.severity,
            'timestamp': alert.timestamp.isoformat()
        })
    
    return JsonResponse({
        'sessions': sessions_data,
        'alerts': alerts_data
    })

@login_required
def api_session_latest_frame(request, session_id):
    """API endpoint to get the latest frame for a session"""
    # Check if user is a teacher
    if request.user.user_type != 'teacher':
        return JsonResponse({'error': 'Access denied'}, status=403)
        
    # Get session object
    session = get_object_or_404(ExamSession, id=session_id)
    
    # Verify that this session belongs to an exam that the teacher owns
    if session.exam.teacher != request.user:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Get latest frame for this session
    try:
        latest_frame = StreamFrame.objects.filter(
            session=session
        ).latest('timestamp')
        
        # Get count of active alerts
        alert_count = Alert.objects.filter(
            session=session,
            is_reviewed=False
        ).count()
        
        return JsonResponse({
            'frame_url': settings.MEDIA_URL + latest_frame.frame_path,
            'timestamp': latest_frame.timestamp.isoformat(),
            'has_active_alerts': alert_count > 0,
            'alert_count': alert_count
        })
    except StreamFrame.DoesNotExist:
        return JsonResponse({
            'error': 'No frames available',
            'has_active_alerts': False,
            'alert_count': 0
        }, status=404)

@login_required
@csrf_protect
@require_POST
def api_mark_alert_reviewed(request, alert_id):
    """API endpoint to mark an alert as reviewed"""
    # Check if user is a teacher
    if request.user.user_type != 'teacher':
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    alert = get_object_or_404(Alert, id=alert_id)
    
    # Verify that this alert belongs to an exam that the teacher owns
    if alert.session.exam.teacher != request.user:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    alert.is_reviewed = True
    alert.reviewed_at = timezone.now()
    alert.reviewed_by = request.user
    alert.save()
    
    return JsonResponse({'success': True})