from django.shortcuts import redirect
from django.urls import reverse

class RoleBasedAccessControlMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if request.path.startswith('/teacher/') and request.user.user_type != 'teacher':
                return redirect(reverse('Users:access_denied'))
            elif request.path.startswith('/student/') and request.user.user_type != 'student':
                return redirect(reverse('Users:access_denied'))
        response = self.get_response(request)
        return response
