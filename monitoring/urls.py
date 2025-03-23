from django.urls import path
from . import views

app_name = 'monitoring'

urlpatterns = [
    path('monitoring/dashboard', views.monitoring_dashboard, name='examdashboard'),
    path('monitoring/exam/<int:exam_id>', views.exam_monitor, name='exam_monitor'),
    path('monitoring/exam/<int:exam_id>/student/<int:student_id>', views.monitoring_student, name='monitor_student'),
    path('monitoring/alert/<int:alert_id>/review', views.mark_alert_reviewed, name='mark_alert_reviewed'),
    # Update the path to match what JavaScript is expecting
    path('monitoring/frame-upload/', views.upload_frame, name='upload_frame'),
    
    # API endpoints for exam monitoring interface
    path('monitoring/api/exam/<int:exam_id>/sessions/', views.api_exam_sessions, name='api_exam_sessions'),
    path('monitoring/api/session/<int:session_id>/latest-frame/', views.api_session_latest_frame, name='api_session_latest_frame'),
    path('monitoring/alert/<int:alert_id>/mark-reviewed/', views.api_mark_alert_reviewed, name='api_mark_alert_reviewed'),
]