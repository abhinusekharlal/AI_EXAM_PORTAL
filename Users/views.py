from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout, update_session_auth_hash
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.core.mail import send_mail, EmailMessage
from django.contrib import messages
from datetime import timedelta
from .models import User, UserSession
from .forms import UserForm, LoginForm, ProfileForm
from classroom.models import Classroom, Exam
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.forms import PasswordChangeForm
from .face_recognition_utils import register_face, verify_face
import json
import logging
import smtplib
from socket import gaierror
from results.models import ExamResult
from django.urls import reverse

# Get a logger instance
logger = logging.getLogger(__name__)

# Create your views here.
def index(request):
    return render(request, "Users/index.html")

@login_required
def dashboard(request, username):
    if request.user.user_type == 'student':
        return student_dashboard(request, username)
    elif request.user.user_type == 'teacher':
        return teacher_dashboard(request, username)
    else:
        return redirect('Users:access_denied')

# Add help view
@login_required
def help_page(request):
    """Display help content based on user type"""
    user_type = request.user.user_type
    context = {
        'is_student': request.user.is_student(),
        'is_teacher': request.user.is_teacher(),
        'user': request.user
    }
    return render(request, 'Users/help.html', context)

def register(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        print(f'Form is valid: {form.is_valid()}')
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.is_active = False
                user.email_verification_token = get_random_string(64)
                user.email_token_created_at = timezone.now()
                user.save()
                
                # Fix: Use reverse() to generate the correct URL with namespace
                verification_url = request.build_absolute_uri(
                    reverse('Users:verify-email', args=[user.email_verification_token])
                )
                logger.info(f"Generated verification URL: {verification_url}")
                
                # Create email message
                email_subject = 'Verify your AI Exam Portal account'
                email_body = f'''Please click this link to verify your email: {verification_url}
                Link expires in 24 hours.'''
                
                try:
                    # Try sending with EmailMessage for more control and debugging
                    email = EmailMessage(
                        subject=email_subject,
                        body=email_body,
                        from_email='noreply@aiexamportal.com',
                        to=[user.email],
                    )
                    logger.info(f"Attempting to send email to {user.email}")
                    
                    # Add connection debugging
                    try:
                        connection = email.get_connection()
                        connection.open()
                        logger.info("Successfully opened email connection")
                        
                        # Actually send the email
                        email.send(fail_silently=False)
                        logger.info(f"Successfully sent verification email to {user.email}")
                        connection.close()
                        
                        messages.success(request, 'Registration successful! Please check your email to verify your account.')
                        return redirect('Users:email_verification_sent')
                        
                    except smtplib.SMTPException as smtp_e:
                        logger.error(f"SMTP Error: {str(smtp_e)}")
                        # We'll still redirect even if email fails, but with a different message
                        messages.warning(request, 'Account created but verification email could not be sent. Please contact support.')
                        return redirect('Users:email_verification_sent')
                    except gaierror as ge:
                        logger.error(f"DNS lookup failed: {str(ge)}")
                        messages.warning(request, 'Account created but verification email could not be sent. Please contact support.')
                        return redirect('Users:email_verification_sent')
                    except Exception as conn_e:
                        logger.error(f"Connection error: {str(conn_e)}")
                        messages.warning(request, 'Account created but verification email could not be sent. Please contact support.')
                        return redirect('Users:email_verification_sent')
                    
                except Exception as e:
                    logger.error(f"Failed to send verification email: {str(e)}")
                    # Log SMTP settings for debugging
                    from django.conf import settings
                    logger.info(f"SMTP Settings: Host: {settings.EMAIL_HOST}, Port: {settings.EMAIL_PORT}, User: {settings.EMAIL_HOST_USER}, TLS: {settings.EMAIL_USE_TLS}, From Email: {settings.DEFAULT_FROM_EMAIL}")
                    
                    # Important change: Don't delete the user, just show warning and redirect
                    messages.warning(request, 'Account created but verification email could not be sent. Please contact support.')
                    return redirect('Users:email_verification_sent')
                    
            except Exception as e:
                logger.error(f"Error during registration: {str(e)}")
                messages.error(request, "An error occurred during registration. Please try again.")
                return render(request, 'Users/register.html', {'form': form})
        else:
            return render(request, 'Users/register.html', {'form': form})
            
    return render(request, 'Users/register.html', {'form': UserForm()})

# Add a test email view to help diagnose email issues
def test_email(request):
    """Test email functionality directly"""
    if not request.user.is_authenticated or not request.user.is_staff:
        return HttpResponse("Unauthorized", status=401)
    
    email = request.GET.get('email', None)
    if not email:
        return HttpResponse("No email provided", status=400)
    
    try:
        # Create and send a test email
        email_subject = 'AI Exam Portal - Test Email'
        email_body = 'This is a test email from AI Exam Portal.'
        
        from django.conf import settings
        logger.info(f"SMTP Settings:")
        logger.info(f"Host: {settings.EMAIL_HOST}")
        logger.info(f"Port: {settings.EMAIL_PORT}")
        logger.info(f"User: {settings.EMAIL_HOST_USER}")
        logger.info(f"TLS: {settings.EMAIL_USE_TLS}")
        logger.info(f"From Email: {settings.DEFAULT_FROM_EMAIL}")
        
        test_email = EmailMessage(
            subject=email_subject,
            body=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        test_email.send(fail_silently=False)
        
        return HttpResponse(f"Test email sent to {email}")
    except Exception as e:
        return HttpResponse(f"Failed to send test email: {str(e)}", status=500)

def verify_email(request, token):
    try:
        # First validate token length to prevent DB lookups with invalid tokens
        if len(token) != 64:
            messages.error(request, 'Invalid verification link.')
            return render(request, 'Users/verify_email.html')
            
        user = User.objects.get(email_verification_token=token)
        
        # Check if token is expired (24 hours)
        if timezone.now() > user.email_token_created_at + timedelta(hours=24):
            messages.error(request, 'Verification link expired. Please register again.')
            user.delete()
            return render(request, 'Users/verify_email.html')
        
        # Check if user is already verified
        if user.is_active and user.is_email_verified:
            messages.info(request, 'Email was already verified. You can login.')
            return render(request, 'Users/verify_email.html')
        
        user.is_active = True
        user.is_email_verified = True
        user.email_verification_token = ''  # Clear the token after use
        user.save()
        
        messages.success(request, 'Email verified successfully. You can now login.')
        
    except User.DoesNotExist:
        messages.error(request, 'Invalid verification link.')
    except Exception as e:
        logger.error(f"Error during email verification: {str(e)}")
        messages.error(request, 'An error occurred during verification. Please try again.')
    
    return render(request, 'Users/verify_email.html')

def login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            
            try:
                # First check if user exists and get their status
                user = User.objects.get(username=username)
                
                if not user.is_active:
                    # Check if they need to verify email
                    if user.email_verification_token:
                        if timezone.now() > user.email_token_created_at + timedelta(hours=24):
                            # Token expired, they need to register again
                            messages.error(request, 'Your verification link has expired. Please register again.')
                            user.delete()
                            return render(request, 'Users/login.html', {'form': form})
                        else:
                            messages.error(request, 'Please verify your email before logging in. Check your inbox for the verification link.')
                            return render(request, 'Users/login.html', {'form': form, 'email': user.email})
                    else:
                        messages.error(request, 'Your account is not active. Please contact support.')
                        return render(request, 'Users/login.html', {'form': form})
                
                # Now try to authenticate
                user = authenticate(request, username=username, password=password)
                if user is not None:
                    # Check for suspicious login attempts (different IP or device)
                    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                    ip = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')
                    user_agent = request.META.get('HTTP_USER_AGENT', '')
                    
                    # Check recent sessions
                    previous_sessions = UserSession.objects.filter(
                        user=user, 
                        is_active=True
                    ).order_by('-created_at')[:5]
                    
                    suspicious_login = False
                    for session in previous_sessions:
                        if session.ip_address != ip and session.user_agent != user_agent:
                            suspicious_login = True
                            break
                    
                    auth_login(request, user)
                    
                    if suspicious_login:
                        messages.warning(
                            request, 
                            "We noticed a login from a new location or device. "
                            "If this wasn't you, please change your password immediately."
                        )
                    
                    # Check for concurrent sessions for students
                    if user.is_student():
                        other_active_sessions = UserSession.objects.filter(
                            user=user,
                            is_active=True
                        ).exclude(session_key=request.session.session_key)
                        
                        if other_active_sessions.exists():
                            messages.info(
                                request,
                                "Note: During exams, you will be automatically logged out from other devices."
                            )
                    
                    return redirect('Users:dashboard', username=user.username)
                else:
                    messages.error(request, 'Invalid password.')
                    
            except User.DoesNotExist:
                messages.error(request, 'No account found with this username.')
            
            return render(request, 'Users/login.html', {'form': form})
    else:
        form = LoginForm()
    return render(request, 'Users/login.html', {'form': form})

def email_verification_sent(request):
    return render(request, 'Users/email_verification_sent.html')
def logout_view(request):
    if request.user.is_authenticated and request.session.session_key:
        # Mark the current session as inactive
        try:
            user_session = UserSession.objects.get(
                user=request.user,
                session_key=request.session.session_key
            )
            user_session.is_active = False
            user_session.save()
        except UserSession.DoesNotExist:
            pass
    
    logout(request)
    return redirect('Users:index')

@login_required
def student_dashboard(request, username):
    if request.user.user_type != 'student':
        return redirect('Users:access_denied')
    
    enrolled_classes = Classroom.objects.filter(students=request.user)
    
    # Get the completed exams (that have results)
    completed_exam_ids = ExamResult.objects.filter(student=request.user).values_list('exam_id', flat=True)
    
    # Get upcoming exams that haven't been completed
    upcoming_exams = Exam.objects.filter(
        exam_class__students=request.user
    ).exclude(
        id__in=completed_exam_ids
    ).order_by('exam_date')
    
    # Get exam results for past exams
    past_exam_results = ExamResult.objects.filter(
        student=request.user
    ).select_related('exam').order_by('-completion_time')
    
    # Get performance trend data
    performance_trend = []
    if past_exam_results:
        for i, result in enumerate(past_exam_results[:5]):  # Last 5 exams
            performance_trend.append({
                'exam_name': result.exam.exam_name,
                'score': result.score
            })
        performance_trend.reverse()  # Show oldest to newest
        
    # Calculate overall statistics
    total_exams = past_exam_results.count()
    if total_exams > 0:
        passed_exams = past_exam_results.filter(status='passed').count()
        failed_exams = past_exam_results.filter(status='failed').count()
        flagged_exams = past_exam_results.filter(is_flagged=True).count()
        avg_score = sum(result.score for result in past_exam_results) / total_exams
    else:
        passed_exams = failed_exams = flagged_exams = 0
        avg_score = 0
    
    context = {
        'groups': request.user.groups.all(),
        'permissions': request.user.user_permissions.all(),
        'is_student': request.user.is_student(),
        'is_teacher': request.user.is_teacher(),
        'student_name': request.user.get_full_name(),
        'email': request.user.email,
        'username': request.user.username,
        'uuid': request.user.id,
        'classrooms': enrolled_classes,
        'upcoming_exams': upcoming_exams,
        'past_exam_results': past_exam_results,
        'total_exams': total_exams,
        'passed_exams': passed_exams,
        'failed_exams': failed_exams,
        'flagged_exams': flagged_exams,
        'avg_score': round(avg_score, 1),
        'performance_trend': performance_trend,
    }
    return render(request, 'Users/student_dashboard.html', context)

@login_required
def teacher_dashboard(request, username):
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
    
    classrooms = Classroom.objects.filter(teacher=request.user)
    upcoming_exams = Exam.objects.filter(exam_class__teacher=request.user).order_by('exam_date')
    exam = Exam.objects.filter(exam_class__teacher=request.user)
    context = {
        'groups': request.user.groups.all(),
        'permissions': request.user.user_permissions.all(),
        'is_student': request.user.is_student(),
        'is_teacher': request.user.is_teacher(),
        'teacher_name': request.user.get_full_name(),
        'email': request.user.email,
        'username': request.user.username,
        'uuid': request.user.id,
        'classrooms': classrooms,
        'upcoming_exams': upcoming_exams,
    }
    return render(request, 'Users/teacher_dashboard.html', context)


@login_required
def submit_feedback(request):
    if request.method == 'POST':
        feedback = request.POST['feedback']
        request.user.feedback = feedback
        request.user.save()
        return redirect('Users:dashboard', username=request.user.username)
    return render(request, 'Users/submit_feedback.html')
def access_denied(request):
    return render(request, 'Users/access_denied.html')

@login_required
def manage_sessions(request):
    """View for users to see and manage their active login sessions"""
    # Get all active sessions for the current user
    active_sessions = UserSession.objects.filter(user=request.user, is_active=True).order_by('-last_activity')
    
    # Mark current session
    current_session_key = request.session.session_key
    
    context = {
        'active_sessions': active_sessions,
        'current_session_key': current_session_key
    }
    
    return render(request, 'Users/manage_sessions.html', context)

@login_required
def terminate_session(request, session_id):
    """Allow a user to terminate one of their sessions"""
    if request.method == 'POST':
        try:
            session = UserSession.objects.get(id=session_id, user=request.user)
            
            # Don't allow terminating the current session through this view
            if session.session_key == request.session.session_key:
                messages.error(request, "You cannot terminate your current session. Use logout instead.")
                return redirect('Users:manage_sessions')
            
            # Mark session as inactive
            session.is_active = False
            session.save()
            
            # Try to delete the actual Django session
            from django.contrib.sessions.models import Session
            try:
                Session.objects.get(session_key=session.session_key).delete()
            except Session.DoesNotExist:
                pass
                
            messages.success(request, "Session terminated successfully.")
            
        except UserSession.DoesNotExist:
            messages.error(request, "Session not found or already terminated.")
    
    return redirect('Users:manage_sessions')

@login_required
def monitor_student_sessions(request):
    """Allow teachers to monitor active student sessions"""
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
        
    # Get IDs of students in classes taught by this teacher
    teacher_classrooms = Classroom.objects.filter(teacher=request.user)
    student_ids = []
    
    for classroom in teacher_classrooms:
        student_ids.extend(classroom.students.values_list('id', flat=True))
    
    # Get unique student users
    students = User.objects.filter(id__in=student_ids).distinct()
    
    # Get active sessions for these students
    active_student_sessions = UserSession.objects.filter(
        user__in=students,
        is_active=True
    ).select_related('user').order_by('-last_activity')
    
    # Check which sessions are from students taking exams
    from django.contrib.sessions.models import Session
    
    for session in active_student_sessions:
        try:
            django_session = Session.objects.get(session_key=session.session_key)
            session_data = django_session.get_decoded()
            
            # Check if any exam_*_started keys exist in the session
            exam_keys = [k for k in session_data.keys() if k.startswith('exam_') and k.endswith('_started')]
            session.is_exam_session = len(exam_keys) > 0
            
            if session.is_exam_session:
                # Get exam ID from session key
                exam_id = exam_keys[0].replace('exam_', '').replace('_started', '')
                try:
                    exam = Exam.objects.get(id=exam_id)
                    session.exam_name = exam.exam_name
                except Exam.DoesNotExist:
                    session.exam_name = "Unknown Exam"
            
        except Session.DoesNotExist:
            session.is_exam_session = False
    
    context = {
        'active_sessions': active_student_sessions,
        'students': students
    }
    
    return render(request, 'Users/monitor_sessions.html', context)

@login_required
def terminate_student_session(request, session_id):
    """Allow a teacher to terminate a student session"""
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
        
    if request.method == 'POST':
        try:
            session = UserSession.objects.get(id=session_id)
            student = session.user
            
            # Make sure this student is in one of the teacher's classes
            teacher_students = []
            teacher_classrooms = Classroom.objects.filter(teacher=request.user)
            
            for classroom in teacher_classrooms:
                teacher_students.extend(classroom.students.values_list('id', flat=True))
                
            if student.id not in teacher_students:
                messages.error(request, "You can only terminate sessions for your students.")
                return redirect('Users:monitor_student_sessions')
            
            # Mark session as inactive
            session.is_active = False
            session.save()
            
            # Try to delete the actual Django session
            from django.contrib.sessions.models import Session
            try:
                Session.objects.get(session_key=session.session_key).delete()
            except Session.DoesNotExist:
                pass
                
            messages.success(request, f"Session for {student.get_full_name()} terminated successfully.")
            
        except UserSession.DoesNotExist:
            messages.error(request, "Session not found or already terminated.")
    
    return redirect('Users:monitor_student_sessions')

@login_required
@require_POST
def face_registration_view(request):
    """Handle face registration from webcam"""
    if not request.user.is_student():
        return JsonResponse({
            'success': False, 
            'message': 'Face registration is only required for students'
        })
    
    try:
        data = json.loads(request.body)
        image_data = data.get('image_data')
        
        if not image_data:
            return JsonResponse({
                'success': False, 
                'message': 'No image data provided'
            })
        
        success, message = register_face(request.user, image_data)
        return JsonResponse({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error processing request: {str(e)}'
        })

@login_required
@require_POST
def face_verification_view(request):
    """Handle face verification before exam"""
    if not request.user.is_student():
        return JsonResponse({
            'success': True, 
            'message': 'Face verification not required for teachers'
        })
    
    try:
        data = json.loads(request.body)
        image_data = data.get('image_data')
        
        if not image_data:
            return JsonResponse({
                'success': False, 
                'message': 'No image data provided'
            })
        
        verified, message = verify_face(request.user, image_data)
        return JsonResponse({
            'success': verified,
            'message': message
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error processing request: {str(e)}'
        })

@login_required
def face_registration_page(request):
    """Page for students to register their face"""
    if not request.user.is_student():
        messages.error(request, 'Face registration is only available for students')
        return redirect('Users:dashboard', username=request.user.username)
        
    return render(request, 'Users/face_registration.html')

@login_required
def face_verification_page(request, exam_id):
    """Page for students to verify their identity before taking an exam"""
    if not request.user.is_student():
        messages.error(request, 'Access denied')
        return redirect('Users:dashboard', username=request.user.username)
    
    try:
        exam = Exam.objects.get(id=exam_id)
        
        # Check if student is enrolled in the exam's class
        if not exam.exam_class.students.filter(id=request.user.id).exists():
            messages.error(request, 'You are not enrolled in this exam')
            return redirect('Users:dashboard', username=request.user.username)
            
        context = {
            'exam': exam,
            'exam_url': f'/classroom/exam/{exam_id}/'
        }
        
        return render(request, 'Users/face_verification.html', context)
        
    except Exam.DoesNotExist:
        messages.error(request, 'Exam not found')
        return redirect('Users:dashboard', username=request.user.username)

@login_required
def profile(request, username):
    """View and update profile information"""
    # Ensure users can only view and edit their own profiles
    if request.user.username != username:
        messages.error(request, 'You can only view and edit your own profile.')
        return redirect('Users:dashboard', username=request.user.username)
    
    user = request.user
    
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('Users:profile', username=user.username)
    else:
        form = ProfileForm(instance=user)
    
    # Create context based on user type
    context = {
        'form': form,
        'user': user,
        'is_student': user.is_student(),
        'is_teacher': user.is_teacher(),
    }
    
    # Add user type specific information to context
    if user.is_student():
        enrolled_classes = Classroom.objects.filter(students=user)
        upcoming_exams = Exam.objects.filter(exam_class__students=user).order_by('exam_date')
        context.update({
            'enrolled_classes': enrolled_classes,
            'upcoming_exams': upcoming_exams,
        })
    elif user.is_teacher():
        teaching_classes = Classroom.objects.filter(teacher=user)
        exams_created = Exam.objects.filter(teacher=user).count()
        students_count = sum(classroom.students.count() for classroom in teaching_classes)
        context.update({
            'teaching_classes': teaching_classes,
            'exams_created': exams_created,
            'students_count': students_count,
        })
    
    return render(request, 'Users/profile.html', context)

@login_required
def change_password(request):
    """Handle password change requests"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Important: update the session to prevent the user from being logged out
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return JsonResponse({'success': True})
        else:
            errors = {field: errors[0] for field, errors in form.errors.items()}
            return JsonResponse({'success': False, 'errors': errors})
    
    return JsonResponse({'success': False, 'errors': {'form': 'Invalid request method'}}, status=400)

def resend_verification_email(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email, is_email_verified=False)
            
            # Generate new verification token
            user.email_verification_token = get_random_string(64)
            user.email_token_created_at = timezone.now()
            user.save()
            
            # Generate verification URL
            verification_url = request.build_absolute_uri(
                reverse('Users:verify-email', args=[user.email_verification_token])
            )
            
            # Create email message
            email_subject = 'Verify your AI Exam Portal account'
            email_body = f'''Please click this link to verify your email: {verification_url}
            Link expires in 24 hours.'''
            
            try:
                email = EmailMessage(
                    subject=email_subject,
                    body=email_body,
                    from_email='noreply@aiexamportal.com',
                    to=[user.email],
                )
                email.send(fail_silently=False)
                messages.success(request, 'Verification email has been resent. Please check your inbox.')
                
            except Exception as e:
                logger.error(f"Failed to resend verification email: {str(e)}")
                messages.error(request, 'Failed to resend verification email. Please try again later.')
                
        except User.DoesNotExist:
            messages.error(request, 'No unverified account found with this email address.')
    
    return redirect('Users:email_verification_sent')