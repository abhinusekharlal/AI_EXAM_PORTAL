from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login
from .models import User
from .forms import UserForm, LoginForm
# Create your views here.

def index(request):
    return render(request, "Users/index.html")

def register(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('Users:login')
        else:
            return render(request, 'Users/register.html', {'form': form})
    return render(request, 'Users/register.html', {'form': UserForm()})

def login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                auth_login(request, user)
                return redirect('Users:index')
            else:
                return render(request, 'Users/login.html', {'form': form, 'error': 'Invalid username or password'})
    else:
        form = LoginForm()
    return render(request, 'Users/login.html', {'form': form})