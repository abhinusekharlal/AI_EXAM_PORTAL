from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.sessions.models import Session
from .models import UserSession
import re

class RoleBasedAccessControlMiddleware(MiddlewareMixin):
    """Middleware to handle role-based access control."""
    def process_view(self, request, view_func, view_args, view_kwargs):
        # If the user is authenticated, check their role against the URL pattern
        if request.user.is_authenticated:
            # URLs that start with /teacher/ are only accessible to teachers
            if re.match(r'^/teacher/', request.path_info) and not request.user.is_teacher():
                return redirect('Users:access_denied')
            
            # URLs that start with /student/ are only accessible to students
            if re.match(r'^/student/', request.path_info) and not request.user.is_student():
                return redirect('Users:access_denied')
        return None


class SessionTrackingMiddleware(MiddlewareMixin):
    """Middleware to track user sessions and device information."""
    
    def process_request(self, request):
        if not request.user.is_authenticated:
            return None
            
        # Skip for static files and admin URLs
        if request.path.startswith('/static/') or request.path.startswith('/admin/'):
            return None
            
        # Get client IP address
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
            
        # Get user agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Update or create session record
        if request.session.session_key:
            session, created = UserSession.objects.get_or_create(
                user=request.user,
                session_key=request.session.session_key,
                defaults={
                    'ip_address': ip,
                    'user_agent': user_agent,
                    'is_active': True
                }
            )
            
            if not created:
                session.ip_address = ip
                session.user_agent = user_agent
                session.save()
        
        return None


class SingleDeviceSessionMiddleware(MiddlewareMixin):
    """Middleware to enforce single-device login during exams for students."""
    
    def process_request(self, request):
        if not request.user.is_authenticated or not request.user.is_student():
            return None
            
        # Check if user is taking an exam
        is_taking_exam = False
        for key in request.session.keys():
            if key.startswith('exam_') and key.endswith('_started'):
                is_taking_exam = True
                break
                
        if is_taking_exam:
            # Allow the current session, but invalidate all others
            current_sessions = UserSession.objects.filter(
                user=request.user,
                is_active=True
            ).exclude(session_key=request.session.session_key)
            
            if current_sessions.exists():
                # Invalidate all other sessions
                for session in current_sessions:
                    session.is_active = False
                    session.save()
                    
                    # Delete the actual Django session
                    try:
                        Session.objects.get(session_key=session.session_key).delete()
                    except Session.DoesNotExist:
                        pass
                
                # Notify the user that they've been logged out from other devices
                messages.warning(request, "You've been logged out from other devices as only one device is allowed during exams.")
                
        return None
