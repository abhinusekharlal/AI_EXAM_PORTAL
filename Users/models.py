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
    # Face recognition fields
    face_recognition_enabled = models.BooleanField(default=False)
    face_image = models.ImageField(upload_to='face_recognition/', null=True, blank=True)
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

    def __str__(self):
        return self.username
    
    def is_student(self):
        return self.user_type == 'student'
    
    def is_teacher(self):
        return self.user_type == 'teacher'


class UserSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=40, db_index=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    device_info = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Session"
        verbose_name_plural = "User Sessions"

    def __str__(self):
        return f"{self.user.username} - {self.ip_address} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

# Model to store face embeddings for facial recognition
class FaceEmbedding(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='face_embeddings')
    embedding_vector = models.BinaryField()  # Store the serialized embedding
    created_at = models.DateTimeField(auto_now_add=True)
    is_primary = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Face Embedding"
        verbose_name_plural = "Face Embeddings"

    def __str__(self):
        return f"Face embedding for {self.user.username} ({self.created_at.strftime('%Y-%m-%d')})"