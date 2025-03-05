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
    path('profile/<str:username>/', views.profile, name='profile'),
    path('change-password/', views.change_password, name='change_password'),
    path('submit_feedback/', views.submit_feedback, name='submit_feedback'),
    path('access-denied/', views.access_denied, name='access_denied'),
    path('sessions/', views.manage_sessions, name='manage_sessions'),
    path('sessions/terminate/<int:session_id>/', views.terminate_session, name='terminate_session'),
    path('monitor/student-sessions/', views.monitor_student_sessions, name='monitor_student_sessions'),
    path('monitor/terminate-student-session/<int:session_id>/', views.terminate_student_session, name='terminate_student_session'),
    path('help/', views.help_page, name='help'),  # New URL for help page
    
    # Face recognition URLs
    path('face-registration/', views.face_registration_page, name='face_registration_page'),
    path('api/face-register/', views.face_registration_view, name='face_register'),
    path('api/face-verify/', views.face_verification_view, name='face_verify'),
    path('face-verification/<int:exam_id>/', views.face_verification_page, name='face_verification_page'),
    
    # Email testing URL (for debugging)
    path('test-email/', views.test_email, name='test_email'),
]
