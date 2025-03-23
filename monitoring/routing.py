from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/exam-monitor/<int:exam_id>/', consumers.ExamMonitorConsumer.as_asgi()),
    path('ws/exam-monitor-teacher/<int:exam_id>/', consumers.TeacherMonitorConsumer.as_asgi()),
]