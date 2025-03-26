from django.db import models
import uuid
from django.conf import settings

class Classroom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    class_name = models.CharField(max_length=100)
    class_code = models.CharField(max_length=10, unique=True)
    class_description = models.TextField(default='')
    teacher = models.ForeignKey('Users.User', on_delete=models.CASCADE)
    students = models.ManyToManyField('Users.User', related_name='class_students')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.class_name
    
    class Meta:
        verbose_name_plural = 'Classrooms'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.class_code:
            self.class_code = self.generate_class_code()
        super().save(*args, **kwargs)

    def generate_class_code(self):
        return uuid.uuid4().hex[:10].upper()

class Exam(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('completed', 'Completed'),
    )
    
    exam_name = models.CharField(max_length=100)
    exam_class = models.ForeignKey(Classroom, on_delete=models.CASCADE)
    exam_date = models.DateField()
    exam_time = models.TimeField()
    exam_end_time = models.TimeField(default='23:59:59', help_text="When the exam ends")  # Added default value
    visibility_to_students = models.BooleanField(default=True, help_text="Whether students can see this exam before it starts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    teacher = models.ForeignKey('Users.User', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')  # Default changed to draft
    
    def __str__(self):
        return self.exam_name
    
    class Meta:
        verbose_name_plural = 'Exams'
        ordering = ['-exam_date']
        
    @property
    def duration(self):
        """Calculate the duration from start time to end time"""
        from datetime import datetime, timedelta
        start_datetime = datetime.combine(self.exam_date, self.exam_time)
        end_datetime = datetime.combine(self.exam_date, self.exam_end_time)
        
        # Handle if end time is on the next day
        if end_datetime < start_datetime:
            end_datetime = end_datetime + timedelta(days=1)
            
        return end_datetime - start_datetime

OPTION_CHOICES = (
    ('1', 'Option 1'),
    ('2', 'Option 2'),
    ('3', 'Option 3'),
    ('4', 'Option 4'),
)

class Question(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    option1 = models.CharField(max_length=100)
    option2 = models.CharField(max_length=100)
    option3 = models.CharField(max_length=100)
    option4 = models.CharField(max_length=100)
    # Update correct_option to use valid choices and limit max_length accordingly.
    correct_option = models.CharField(max_length=1, choices=OPTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.question_text
    
    class Meta:
        verbose_name_plural = 'Questions'
        ordering = ['-created_at']
