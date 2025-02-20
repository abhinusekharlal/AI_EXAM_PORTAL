from django.urls import path
from . import views

app_name = 'Users'

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('verify-email/<str:token>/', views.verify_email, name='verify-email'),
    path('email-verification-sent/', views.email_verification_sent, name='email_verification_sent'),
    path('dashboard/<str:username>/', views.dashboard, name='dashboard'),
    path('submit_feedback/', views.submit_feedback, name='submit_feedback'),
    path('access-denied/', views.access_denied, name='access_denied'),
]
