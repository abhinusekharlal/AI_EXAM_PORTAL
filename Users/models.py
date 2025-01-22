from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid

class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=200, blank=True)
    email_token_created_at = models.DateTimeField(null=True, blank=True)
    # ...existing code...
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_groups',  # Add related_name to avoid clashes
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_permissions',  # Add related_name to avoid clashes
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )
    classrooms = models.ManyToManyField('classroom.Classroom', related_name='enrolled_students')

    def is_student(self):
        return self.user_type == 'student'
    
    def is_teacher(self):
        return self.user_type == 'teacher'