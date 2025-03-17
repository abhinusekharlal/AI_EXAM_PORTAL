from django.db import models
from django.conf import settings
from classroom.models import Exam
from django.utils import timezone

class ExamSession(models.Model):
    """Model to track student exam sessions for monitoring purposes"""
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='exam_sessions')
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    # Connection tracking
    connection_id = models.CharField(max_length=100, blank=True, null=True)
    
    def __str__(self):
        return f"{self.student.username} - {self.exam.exam_name}"
    
    class Meta:
        unique_together = ['student', 'exam', 'is_active']
        indexes = [
            models.Index(fields=['exam', 'is_active']),
            models.Index(fields=['student', 'is_active']),
        ]


class Alert(models.Model):
    """Model to track monitoring alerts during exam sessions"""
    ALERT_TYPES = [
        ('face_missing', 'Face Not Detected'),
        ('multiple_faces', 'Multiple Faces'),
        ('unknown_face', 'Unknown Person'),
        ('looking_away', 'Looking Away'),
        ('tab_switch', 'Tab Switched'),
        ('suspicious_motion', 'Suspicious Motion'),
        ('phone_detected', 'Phone Detected'),
        ('speaking', 'Speaking Detected'),
        ('unauthorized_object', 'Unauthorized Object'),
        ('other', 'Other Violation'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    session = models.ForeignKey(ExamSession, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, default='medium')
    confidence = models.FloatField(default=0.0)  # AI confidence score (0-1)
    is_reviewed = models.BooleanField(default=False)
    screenshot = models.ImageField(upload_to='monitoring/alerts/', null=True, blank=True)
    
    def __str__(self):
        return f"{self.session.student.username} - {self.get_alert_type_display()}"
    
    class Meta:
        indexes = [
            models.Index(fields=['session', 'timestamp']),
            models.Index(fields=['is_reviewed']),
        ]


class StreamFrame(models.Model):
    session = models.ForeignKey(ExamSession, on_delete=models.CASCADE, related_name='frames')
    frame_path = models.CharField(max_length=255)
    timestamp = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Frame: {self.session.student.get_full_name()} - {self.timestamp}"
