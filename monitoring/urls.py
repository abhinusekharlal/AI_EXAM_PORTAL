from django.urls import path
from . import views

app_name = 'monitoring'

urlpatterns = [
    path('monitoring/dashboard', views.monitoring_dashboard, name='examdashboard'),
    path('monitoring/exam/<int:exam_id>', views.exam_monitor, name='exam_monitor'),
    path('monitoring/exam/<int:exam_id>/student/<int:student_id>', views.monitoring_student, name='monitor_student'),
    path('monitoring/alert/<int:alert_id>/review', views.mark_alert_reviewed, name='mark_alert_reviewed'),
    
    path('monitoring/alert/<int:alert_id>/screenshot/', views.get_alert_screenshot, name='get_alert_screenshot'),
    path('monitoring/frame-upload/', views.upload_frame, name='upload_frame'),
    
    # API endpoints for exam monitoring interface
    path('monitoring/api/exam/<int:exam_id>/sessions/', views.api_exam_sessions, name='api_exam_sessions'),
    path('monitoring/api/exam/<int:exam_id>/details/', views.api_exam_details, name='api_exam_details'),
    path('monitoring/api/session/<int:session_id>/latest-frame/', views.api_session_latest_frame, name='api_session_latest_frame'),
    path('monitoring/alert/<int:alert_id>/mark-reviewed/', views.api_mark_alert_reviewed, name='api_mark_alert_reviewed'),
    
    # Added missing routes
    path('monitoring/exam/<int:exam_id>/mark-all-alerts-reviewed/', views.mark_all_alerts_reviewed, name='mark_all_alerts_reviewed'),
    path('monitoring/api/session/<int:session_id>/activity/', views.api_student_activity, name='api_student_activity'),
    
    # Add these missing endpoints
    path('monitoring/api/session/<int:session_id>/send-warning/', views.api_send_warning, name='api_send_warning'),
    path('monitoring/api/session/<int:session_id>/flag-student/', views.api_flag_student, name='api_flag_student'),
    path('monitoring/api/session/<int:session_id>/pause-exam/', views.api_pause_exam, name='api_pause_exam'),
    path('monitoring/alert/<int:alert_id>/reject/', views.api_reject_alert, name='api_reject_alert'),
    
    # Export monitoring data
    path('monitoring/exam/<int:exam_id>/export-data/', views.export_session_data, name='export_session_data'),
    path('monitoring/session/<int:session_id>/export-activity/', views.export_student_activity, name='export_student_activity'),
]