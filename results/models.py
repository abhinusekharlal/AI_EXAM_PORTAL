from django.db import models
from django.conf import settings
from classroom.models import Exam, Question
from django.utils import timezone
from monitoring.models import Alert, ExamSession
import json

class ExamResult(models.Model):
    """
    Model to permanently store student exam results including responses and scores
    """
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='exam_results')
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='results')
    
    # Score details
    score = models.FloatField(help_text="Percentage score (0-100)")
    correct_answers = models.PositiveIntegerField(default=0)
    total_questions = models.PositiveIntegerField(default=0)
    
    # Timing information
    start_time = models.DateTimeField()
    completion_time = models.DateTimeField()
    time_taken = models.DurationField(help_text="Total time taken to complete the exam")
    
    # Responses - stored as JSON
    responses = models.JSONField(default=dict, help_text="Student's answers to each question")
    
    # Status
    RESULT_STATUS = (
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('partial', 'Partial'),  # For partially completed exams
        ('flagged', 'Flagged'),  # For exams with suspicious behavior
        ('under_review', 'Under Review'),  # For exams being reviewed by teacher
        ('penalty_applied', 'Penalty Applied'),  # For exams with confirmed violations
    )
    status = models.CharField(max_length=15, choices=RESULT_STATUS, default='failed')
    
    # Flags and penalties
    is_flagged = models.BooleanField(default=False, help_text="Whether this exam was flagged for suspicious behavior")
    is_reviewed = models.BooleanField(default=False, help_text="Whether this exam has been reviewed by the teacher")
    penalty_percentage = models.FloatField(default=0, help_text="Percentage points deducted due to violations")
    original_score = models.FloatField(null=True, blank=True, help_text="Score before penalties were applied")
    
    # Review notes
    teacher_notes = models.TextField(blank=True, help_text="Teacher's notes after reviewing the exam")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'exam']
        ordering = ['-created_at']
        verbose_name = 'Exam Result'
        verbose_name_plural = 'Exam Results'
        indexes = [
            models.Index(fields=['student', 'exam']),
            models.Index(fields=['exam', 'status']),
            models.Index(fields=['is_flagged']),
            models.Index(fields=['is_reviewed']),
        ]
    
    def __str__(self):
        return f"{self.student.username} - {self.exam.exam_name} - {self.score}%"
    
    def save(self, *args, **kwargs):
        # Calculate time_taken if not explicitly set
        if not self.time_taken and self.start_time and self.completion_time:
            self.time_taken = self.completion_time - self.start_time
            
        # Set original_score if it's not set and penalties are being applied
        if self.penalty_percentage > 0 and self.original_score is None:
            self.original_score = self.score + self.penalty_percentage
            
        # Determine pass/fail status based on score (assuming 60% is passing)
        # This could be customized based on exam-specific passing thresholds
        if not self.is_flagged and not self.is_reviewed:
            if self.score >= 60:
                self.status = 'passed'
            else:
                self.status = 'failed'
            
        super().save(*args, **kwargs)
    
    @property
    def duration_in_minutes(self):
        """Return the duration in minutes"""
        if self.time_taken:
            return self.time_taken.total_seconds() / 60
        return 0
    
    @classmethod
    def create_from_submission(cls, student, exam, answers, start_time=None):
        """
        Create an ExamResult instance from exam submission data
        
        Parameters:
            student: User instance of the student
            exam: Exam instance
            answers: Dict mapping question_id to selected_option
            start_time: Start time of the exam (optional)
        """
        # Get all questions for this exam
        questions = Question.objects.filter(exam=exam)
        total_questions = questions.count()
        
        # Calculate correct answers and score
        correct_count = 0
        for question in questions:
            if str(question.id) in answers and str(question.correct_option) == str(answers[str(question.id)]):
                correct_count += 1
        
        # Calculate score as percentage
        score = (correct_count / total_questions) * 100 if total_questions > 0 else 0
        
        # Get completion time (now)
        completion_time = timezone.now()
        
        # Use provided start_time or default to completion_time - estimated duration
        if not start_time:
            # If no start_time provided, estimate based on exam duration
            start_time = completion_time - exam.exam_duration
        
        # Check if there are any alerts for this student's exam session
        try:
            session = ExamSession.objects.get(student=student, exam=exam, is_active=False)
            alerts_count = Alert.objects.filter(session=session).count()
            is_flagged = alerts_count > 0
        except ExamSession.DoesNotExist:
            is_flagged = False
        
        # Set initial status based on flagging
        initial_status = 'flagged' if is_flagged else ('passed' if score >= 60 else 'failed')
        
        # Create and return result
        return cls.objects.create(
            student=student,
            exam=exam,
            score=score,
            correct_answers=correct_count,
            total_questions=total_questions,
            start_time=start_time,
            completion_time=completion_time,
            time_taken=completion_time - start_time,
            responses=answers,
            is_flagged=is_flagged,
            status=initial_status,
        )
    
    def apply_penalty(self, penalty_percentage, notes=""):
        """Apply a penalty to the exam score and update notes"""
        if self.original_score is None:
            self.original_score = self.score
        
        self.score = max(0, self.score - penalty_percentage)
        self.penalty_percentage = penalty_percentage
        
        if notes:
            if self.teacher_notes:
                self.teacher_notes += f"\n\n{notes}"
            else:
                self.teacher_notes = notes
        
        self.status = 'penalty_applied'
        self.is_reviewed = True
        self.save()
    
    def mark_as_reviewed(self, notes="", clear_flag=True):
        """Mark this result as reviewed and optionally clear the flag"""
        if clear_flag:
            self.is_flagged = False
        
        if notes:
            if self.teacher_notes:
                self.teacher_notes += f"\n\n{notes}"
            else:
                self.teacher_notes = notes
        
        self.is_reviewed = True
        
        # If we're clearing the flag, update the status based on score
        if clear_flag:
            if self.score >= 60:
                self.status = 'passed'
            else:
                self.status = 'failed'
        
        self.save()


class ExamViolation(models.Model):
    """
    Model to store confirmed exam violations after teacher review
    """
    VIOLATION_TYPES = [
        ('cheating', 'Cheating'),
        ('unauthorized_assistance', 'Unauthorized Assistance'),
        ('impersonation', 'Impersonation'),
        ('unauthorized_materials', 'Unauthorized Materials'),
        ('communication', 'Unauthorized Communication'),
        ('device_usage', 'Unauthorized Device Usage'),
        ('technical_violation', 'Technical Rule Violation'),
        ('other', 'Other Violation'),
    ]
    
    SEVERITY_LEVELS = [
        ('minor', 'Minor'),
        ('moderate', 'Moderate'),
        ('major', 'Major'),
        ('critical', 'Critical'),
    ]
    
    exam_result = models.ForeignKey(ExamResult, on_delete=models.CASCADE, related_name='violations')
    alert = models.ForeignKey(Alert, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmed_violations')
    violation_type = models.CharField(max_length=30, choices=VIOLATION_TYPES)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, default='moderate')
    penalty_applied = models.FloatField(default=0, help_text="Percentage points deducted for this violation")
    evidence_screenshot = models.ImageField(upload_to='violations/evidence/', null=True, blank=True)
    
    # Who reviewed and confirmed this violation
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='reviewed_violations'
    )
    
    def __str__(self):
        return f"{self.exam_result.student.username} - {self.get_violation_type_display()}"
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['exam_result']),
            models.Index(fields=['violation_type']),
            models.Index(fields=['severity']),
        ]
