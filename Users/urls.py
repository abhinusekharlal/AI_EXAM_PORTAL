from django.urls import path
from . import views

app_name = 'Users'

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login, name='login'),
    path('register/', views.register, name='register'),
    path('verify-email/<str:token>/', views.verify_email, name='verify-email'),
    path('email-verification-sent/', views.email_verification_sent, name='email_verification_sent'),
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('access-denied/', views.access_denied, name='access_denied'),
]
