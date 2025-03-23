from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, F
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_protect
from django.core.paginator import Paginator
from django.conf import settings
from django.contrib import messages
from classroom.models import Exam, Question
from Users.models import User
from Users.middleware import UserSession
from monitoring.models import ExamSession, Alert, StreamFrame
from .frame_processor import FrameProcessor
import datetime
import json
import base64
import os
import uuid
import logging

# Set up logging
logger = logging.getLogger(__name__)

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
    
    # Include exams that started within last 24 hours even if exam date is in past
    recent_time_threshold = now - datetime.timedelta(hours=24)
    
    active_exams = Exam.objects.filter(
        Q(teacher=request.user) &
        (Q(exam_date__gte=today) | 
         Q(exam_date=today - datetime.timedelta(days=1), exam_time__gte=recent_time_threshold.time()))
    ).order_by('exam_date', 'exam_time')
    
    # Get active exam sessions for exams taught by this teacher
    active_sessions = ExamSession.objects.filter(
        exam__in=active_exams,
        is_active=True
    ).select_related('student', 'exam').order_by('-started_at')
    
    # Get recent alerts for active sessions with aggregated counts
    recent_alerts = Alert.objects.filter(
        session__in=active_sessions,
        is_reviewed=False
    ).select_related('session', 'session__student', 'session__exam').order_by('-timestamp')[:20]
    
    # Get alert counts per exam
    alert_counts = Alert.objects.filter(
        session__exam__in=active_exams, 
        is_reviewed=False
    ).values('session__exam').annotate(count=Count('id'))
    
    # Create a dictionary of exam IDs to alert counts
    alert_counts_dict = {item['session__exam']: item['count'] for item in alert_counts}
    
    context = {
        'active_exams': active_exams,
        'active_sessions': active_sessions,
        'recent_alerts': recent_alerts,
        'alert_counts_dict': alert_counts_dict,
        'current_time': now,
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
    
    # Calculate session metrics
    total_sessions = active_sessions.count()
    connected_sessions = active_sessions.filter(
        last_activity__gte=timezone.now() - datetime.timedelta(minutes=2)
    ).count()
    
    # Get active alerts for this exam's sessions
    active_alerts = Alert.objects.filter(
        session__exam=exam,
        is_reviewed=False
    ).select_related('session', 'session__student').order_by('-timestamp')
    
    # Get alert counts by severity
    high_severity_count = active_alerts.filter(severity='critical').count()
    medium_severity_count = active_alerts.filter(severity='warning').count()
    low_severity_count = active_alerts.filter(severity='info').count()
    
    # Get flagged students (students with critical alerts)
    # Use proper query with joins to get students with critical alerts
    active_session_ids = active_sessions.values_list('id', flat=True)
    flagged_students = User.objects.filter(
        exam_sessions__id__in=active_session_ids,
        exam_sessions__alerts__severity='critical', 
        exam_sessions__alerts__is_reviewed=False
    ).distinct()
    
    context = {
        'exam': exam,
        'active_sessions': active_sessions,
        'active_alerts': active_alerts,
        'student_filter': student_filter,
        'total_sessions': total_sessions,
        'connected_sessions': connected_sessions,
        'disconnected_sessions': total_sessions - connected_sessions,
        'high_severity_count': high_severity_count,
        'medium_severity_count': medium_severity_count,
        'low_severity_count': low_severity_count,
        'flagged_students': flagged_students,
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
        
        # Get alerts for this session
        alerts = Alert.objects.filter(session=session).order_by('-timestamp')
        
        # Get the most recent alerts of each type
        recent_alerts_by_type = {}
        for alert in alerts:
            if alert.alert_type not in recent_alerts_by_type:
                recent_alerts_by_type[alert.alert_type] = alert
        
        # Get recent frames for timeline view
        recent_frames = StreamFrame.objects.filter(
            session=session
        ).order_by('-timestamp')[:10]
        
        context = {
            'exam': exam,
            'student': student,
            'session': session,
            'alerts': alerts,
            'recent_alerts_by_type': recent_alerts_by_type.values(),
            'recent_frames': recent_frames,
            'is_active': (timezone.now() - session.last_activity).total_seconds() < 120,
        }
        
        return render(request, 'monitoring/monitor_student.html', context)
        
    except ExamSession.DoesNotExist:
        # Redirect back to exam monitoring with a message indicating no active session
        messages.warning(request, f"No active exam session found for {student.get_full_name() or student.username}")
        return redirect('monitoring:exam_monitor', exam_id=exam_id)

@login_required
@require_POST
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
    
    next_url = request.META.get('HTTP_REFERER', 'monitoring:monitoring_dashboard')
    
    # Check if this is an AJAX request
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
        
    return redirect(next_url)

@login_required
@require_POST
def mark_all_alerts_reviewed(request, exam_id):
    """
    Mark all alerts for an exam as reviewed
    """
    # Check if user is a teacher
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
    
    # Get exam object and verify ownership
    exam = get_object_or_404(Exam, id=exam_id)
    if exam.teacher != request.user:
        return redirect('Users:access_denied')
    
    # Update all unreviewed alerts for this exam
    updated_count = Alert.objects.filter(
        session__exam=exam,
        is_reviewed=False
    ).update(
        is_reviewed=True,
        reviewed_at=timezone.now(),
        reviewed_by=request.user
    )
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'count': updated_count
        })
    
    return redirect('monitoring:exam_monitor', exam_id=exam_id)

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
        logger.error(f"Error processing frame upload: {str(e)}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@login_required
@require_GET
def api_exam_sessions(request, exam_id):
    """API endpoint to get active sessions for an exam"""
    logger = logging.getLogger(__name__)
    
    try:
        # Check if user is a teacher
        if request.user.user_type != 'teacher':
            logger.warning(f"Non-teacher user {request.user.id} attempted to access exam sessions")
            return JsonResponse({'error': 'Access denied - must be a teacher'}, status=403)
        
        try:
            # Get exam object and verify ownership
            exam = get_object_or_404(Exam, id=exam_id)
            if exam.teacher != request.user:
                logger.warning(f"User {request.user.id} attempted to access exam {exam_id} they don't own")
                return JsonResponse({'error': 'Access denied - not the exam owner'}, status=403)
        except Exam.DoesNotExist:
            logger.warning(f"Exam not found in api_exam_sessions. exam_id: {exam_id}")
            return JsonResponse({'error': 'Exam not found'}, status=404)
            
        try:
            # Get active sessions for this exam
            active_sessions = ExamSession.objects.filter(
                exam=exam,
                is_active=True
            ).select_related('student')
            
            # Format sessions for JSON response
            sessions_data = []
            for session in active_sessions:
                # Calculate time inactive in seconds
                inactive_seconds = (timezone.now() - session.last_activity).total_seconds() if session.last_activity else None
                
                sessions_data.append({
                    'id': session.id,
                    'student_id': session.student.id,
                    'student_name': session.student.get_full_name() or session.student.username,
                    'started_at': session.started_at.isoformat(),
                    'last_activity': session.last_activity.isoformat() if session.last_activity else None,
                    'inactive_seconds': inactive_seconds,
                    'is_active': session.is_active,
                    'is_connected': inactive_seconds is not None and inactive_seconds < 120
                })
        except Exception as e:
            logger.error(f"Error fetching active sessions: {str(e)}", exc_info=True)
            return JsonResponse({'error': 'Error fetching active sessions'}, status=500)

        try:
            # Get recent alerts
            recent_alerts = Alert.objects.filter(
                session__exam=exam,
                is_reviewed=False
            ).select_related('session', 'session__student').order_by('-timestamp')[:30]
            
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
                    'confidence': alert.confidence,
                    'timestamp': alert.timestamp.isoformat(),
                    'has_screenshot': bool(alert.screenshot)
                })
        except Exception as e:
            logger.error(f"Error fetching alerts: {str(e)}", exc_info=True)
            alerts_data = []

        # Calculate stats
        stats = {
            'total_students': len(sessions_data),
            'connected_students': sum(1 for session in sessions_data if session['is_connected']),
            'alert_count': len(alerts_data),
            'high_severity_count': sum(1 for alert in alerts_data if alert['severity'] == 'critical'),
            'medium_severity_count': sum(1 for alert in alerts_data if alert['severity'] == 'warning'),
            'low_severity_count': sum(1 for alert in alerts_data if alert['severity'] == 'info')
        }
        
        return JsonResponse({
            'sessions': sessions_data,
            'alerts': alerts_data,
            'stats': stats,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in api_exam_sessions: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)

@login_required
@require_GET
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
        
        # Get count of active alerts and their details
        alerts = Alert.objects.filter(
            session=session,
            is_reviewed=False
        )
        alert_count = alerts.count()
        
        # Get details of most recent alert
        latest_alert = alerts.order_by('-timestamp').first()
        
        # Calculate inactivity time
        inactive_seconds = (timezone.now() - session.last_activity).total_seconds() if session.last_activity else None
        is_connected = inactive_seconds is not None and inactive_seconds < 120
        
        return JsonResponse({
            'frame_url': settings.MEDIA_URL + latest_frame.frame_path,
            'timestamp': latest_frame.timestamp.isoformat(),
            'has_active_alerts': alert_count > 0,
            'alert_count': alert_count,
            'latest_alert': {
                'type': latest_alert.alert_type,
                'description': latest_alert.description,
                'severity': latest_alert.severity,
                'timestamp': latest_alert.timestamp.isoformat()
            } if latest_alert else None,
            'inactive_seconds': inactive_seconds,
            'is_connected': is_connected
        })
    except StreamFrame.DoesNotExist:
        return JsonResponse({
            'error': 'No frames available',
            'has_active_alerts': False,
            'alert_count': 0,
            'is_connected': False
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
    
    return JsonResponse({
        'success': True, 
        'alert_id': alert_id,
        'reviewed_at': alert.reviewed_at.isoformat()
    })

@login_required
@require_GET
def api_student_activity(request, session_id):
    """API endpoint to get activity history for a student session"""
    # Check if user is a teacher
    if request.user.user_type != 'teacher':
        return JsonResponse({'error': 'Access denied'}, status=403)
        
    # Get session object
    session = get_object_or_404(ExamSession, id=session_id)
    
    # Verify that this session belongs to an exam that the teacher owns
    if session.exam.teacher != request.user:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Get time range from query parameters
    time_range_minutes = request.GET.get('minutes', 30)
    try:
        time_range_minutes = int(time_range_minutes)
    except ValueError:
        time_range_minutes = 30
    
    # Get alerts within time range
    time_threshold = timezone.now() - datetime.timedelta(minutes=time_range_minutes)
    alerts = Alert.objects.filter(
        session=session,
        timestamp__gte=time_threshold
    ).order_by('-timestamp')
    
    # Get frames within time range (limit to avoid performance issues)
    frames = StreamFrame.objects.filter(
        session=session,
        timestamp__gte=time_threshold
    ).order_by('-timestamp')[:60]  # Limit to 60 frames
    
    # Format data for JSON response
    activity_data = {
        'student_name': session.student.get_full_name() or session.student.username,
        'exam_name': session.exam.exam_name,
        'start_time': session.started_at.isoformat(),
        'last_activity': session.last_activity.isoformat() if session.last_activity else None,
        'alerts': [{
            'id': alert.id,
            'type': alert.alert_type,
            'description': alert.description,
            'severity': alert.severity,
            'timestamp': alert.timestamp.isoformat(),
            'is_reviewed': alert.is_reviewed,
            'has_screenshot': bool(alert.screenshot)
        } for alert in alerts],
        'frames': [{
            'id': frame.id,
            'url': settings.MEDIA_URL + frame.frame_path,
            'timestamp': frame.timestamp.isoformat()
        } for frame in frames]
    }
    
    return JsonResponse(activity_data)

@login_required
@csrf_protect
@require_POST
def api_send_warning(request, session_id):
    """API endpoint to send a warning to a student during an exam"""
    # Check if user is a teacher
    if request.user.user_type != 'teacher':
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Get session object
    session = get_object_or_404(ExamSession, id=session_id)
    
    # Verify that this session belongs to an exam that the teacher owns
    if session.exam.teacher != request.user:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    try:
        data = json.loads(request.body)
        message = data.get('message')
        priority = data.get('priority', 'normal')
        
        if not message:
            return JsonResponse({'error': 'Message is required'}, status=400)
        
        # Create warning notification record
        warning = Warning.objects.create(
            session=session,
            message=message,
            priority=priority,
            sent_by=request.user,
            sent_at=timezone.now()
        )
        
        # In a real implementation, this would send the warning to the student in real-time
        # For example, using WebSockets/Django Channels
        
        return JsonResponse({
            'success': True,
            'warning_id': warning.id,
            'sent_at': warning.sent_at.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error sending warning: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@csrf_protect
@require_POST
def api_flag_student(request, session_id):
    """API endpoint to flag a student for review"""
    # Check if user is a teacher
    if request.user.user_type != 'teacher':
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Get session object
    session = get_object_or_404(ExamSession, id=session_id)
    
    # Verify that this session belongs to an exam that the teacher owns
    if session.exam.teacher != request.user:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    try:
        data = json.loads(request.body)
        reason = data.get('reason')
        severity = data.get('severity', 'medium')
        
        if not reason:
            return JsonResponse({'error': 'Reason is required'}, status=400)
        
        # Create flag record
        flag = Flag.objects.create(
            session=session,
            reason=reason,
            severity=severity,
            flagged_by=request.user,
            flagged_at=timezone.now()
        )
        
        # Also create an alert to maintain consistency
        alert = Alert.objects.create(
            session=session,
            alert_type='manual_flag',
            description=f"Manually flagged: {reason}",
            severity='critical' if severity == 'high' else 'warning',
            timestamp=timezone.now()
        )
        
        return JsonResponse({
            'success': True,
            'flag_id': flag.id,
            'alert_id': alert.id,
            'flagged_at': flag.flagged_at.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error flagging student: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_GET
def export_session_data(request, exam_id):
    """Export monitoring data for an exam"""
    # Check if user is a teacher
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
        
    # Get exam object and verify ownership
    exam = get_object_or_404(Exam, id=exam_id)
    if exam.teacher != request.user:
        return redirect('Users:access_denied')
    
    # Get all sessions for this exam
    sessions = ExamSession.objects.filter(exam=exam).select_related('student')
    
    # Export format depends on requested format (csv or json)
    export_format = request.GET.get('format', 'csv')
    
    if export_format == 'json':
        # Generate JSON export
        data = {
            'exam_name': exam.exam_name,
            'exam_date': exam.exam_date.isoformat(),
            'exam_time': str(exam.exam_time),
            'sessions': []
        }
        
        for session in sessions:
            # Get alerts for this session
            alerts = Alert.objects.filter(session=session).order_by('-timestamp')
            
            session_data = {
                'student_name': session.student.get_full_name(),
                'student_email': session.student.email,
                'started_at': session.started_at.isoformat(),
                'ended_at': session.ended_at.isoformat() if session.ended_at else None,
                'is_active': session.is_active,
                'alerts': [{
                    'alert_type': alert.alert_type,
                    'description': alert.description,
                    'severity': alert.severity,
                    'timestamp': alert.timestamp.isoformat(),
                    'is_reviewed': alert.is_reviewed
                } for alert in alerts]
            }
            
            data['sessions'].append(session_data)
        
        response = JsonResponse(data, json_dumps_params={'indent': 2})
        response['Content-Disposition'] = f'attachment; filename="{exam.exam_name}_monitoring_data.json"'
        return response
    else:
        # Generate CSV export (default)
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{exam.exam_name}_monitoring_data.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Student Name', 'Email', 'Started At', 'Ended At', 'Alert Type', 'Alert Description', 'Severity', 'Timestamp', 'Reviewed'])
        
        for session in sessions:
            alerts = Alert.objects.filter(session=session).order_by('-timestamp')
            
            if alerts:
                for alert in alerts:
                    writer.writerow([
                        session.student.get_full_name(),
                        session.student.email,
                        session.started_at,
                        session.ended_at,
                        alert.alert_type,
                        alert.description,
                        alert.severity,
                        alert.timestamp,
                        'Yes' if alert.is_reviewed else 'No'
                    ])
            else:
                # Write a row for sessions with no alerts
                writer.writerow([
                    session.student.get_full_name(),
                    session.student.email,
                    session.started_at,
                    session.ended_at,
                    'N/A', 'No alerts', 'N/A', 'N/A', 'N/A'
                ])
        
        return response