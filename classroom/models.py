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
    exam_name = models.CharField(max_length=100)
    exam_class = models.ForeignKey(Classroom, on_delete=models.CASCADE)
    exam_date = models.DateField()
    exam_time = models.TimeField()
    exam_duration = models.DurationField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    teacher = models.ForeignKey('Users.User', on_delete=models.CASCADE)
    
    def __str__(self):
        return self.exam_name

    class Meta:
        verbose_name_plural = 'Exams'
        ordering = ['-exam_date']

class Question(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    option1 = models.CharField(max_length=100)
    option2 = models.CharField(max_length=100)
    option3 = models.CharField(max_length=100)
    option4 = models.CharField(max_length=100)
    correct_option = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.question_text
    
    class Meta:
        verbose_name_plural = 'Questions'
        ordering = ['-created_at']
