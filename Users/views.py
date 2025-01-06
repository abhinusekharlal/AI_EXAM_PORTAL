from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.core.mail import send_mail
from django.contrib import messages
from datetime import timedelta
from .models import User
from .forms import UserForm, LoginForm
from django.contrib.auth.decorators import login_required
# Create your views here.

def index(request):
    return render(request, "Users/index.html")

def register(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.email_verification_token = get_random_string(64)
            user.email_token_created_at = timezone.now()
            user.save()

            verification_url = f"{request.scheme}://{request.get_host()}/verify-email/{user.email_verification_token}"
            send_mail(
                'Verify your AI Exam Portal account',
                f'Please click this link to verify your email: {verification_url}\nLink expires in 24 hours.',
                'noreply@aiexamportal.com',
                [user.email],
                fail_silently=False,
            )
            return render(request, 'Users/verify_email.html', {'email': user.email})
        else:
            return render(request, 'Users/register.html', {'form': form})
    return render(request, 'Users/register.html', {'form': UserForm()})

def verify_email(request, token):
    try:
        user = User.objects.get(email_verification_token=token)
        
        # Check if token is expired (24 hours)
        if timezone.now() > user.email_token_created_at + timedelta(hours=24):
            messages.error(request, 'Verification link expired. Please register again.')
            user.delete()
            return render(request, 'Users/verify_email.html')
        
        user.is_active = True
        user.is_email_verified = True
        user.email_verification_token = ''
        user.save()
        messages.success(request, 'Email verified successfully. You can now login.')
        
    except User.DoesNotExist:
        messages.error(request, 'Invalid verification link.')
    
    return render(request, 'Users/verify_email.html')

def login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                if not user.is_active:
                    return render(request, 'Users/login.html', 
                                  {'form': form, 'error': 'Please verify your email first.'})
                auth_login(request, user)
                return redirect('Users:index')
            else:
                return render(request, 'Users/login.html', 
                              {'form': form, 'error': 'Invalid credentials'})
    else:
        form = LoginForm()
    return render(request, 'Users/login.html', {'form': form})

def email_verification_sent(request):
    return render(request, 'Users/email_verification_sent.html')
def logout_view(request):
    logout(request)
    return redirect('Users:index')
@login_required
def student_dashboard(request):
    if request.user.user_type != 'student':
        return redirect('Users:access_denied')
    context = {
        'groups': request.user.groups.all(),
        'permissions': request.user.user_permissions.all(),
        'is_student': request.user.is_student(),
        'is_teacher': request.user.is_teacher(),
        'student_name': request.user.get_full_name(),
        'email': request.user.email,
        'username': request.user.username,
        'uuid': request.user.id,
    }
    return render(request, 'Users/student_dashboard.html', context)

@login_required
def teacher_dashboard(request):
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
    return render(request, 'Users/teacher_dashboard.html')

def access_denied(request):
    return render(request, 'Users/access_denied.html')