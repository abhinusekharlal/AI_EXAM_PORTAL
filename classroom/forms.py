from django import forms

from Users.models import User
from .models import Classroom, Exam, Question
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError


class ClassroomForm(forms.ModelForm):
    class Meta:
        model = Classroom
        fields = ['class_name', 'class_description']

class JoinClassForm(forms.Form):
    class_code = forms.CharField(max_length=10, required=True)

class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['question_text', 'option1', 'option2', 'option3', 'option4', 'correct_option']

def validate_future_date(value):
    if value < timezone.now().date():
        raise ValidationError("The date cannot be in the past.")

class ExamForm(forms.ModelForm):
    exam_date = forms.DateField(
        widget=forms.DateInput(format="%Y-%m-%d",
                               attrs={'type': 'date',
                                      'min': str(timezone.now().date()),
                                      'max': str((timezone.now() + timedelta(days=365)).date())}),
        help_text='Select a date',
        input_formats=["%Y-%m-%d"],
        validators=[validate_future_date],
    )
    exam_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time'}),
        help_text='Select a time'
    )
    exam_duration = forms.DurationField(
        help_text='Enter duration in the format HH:MM:SS'
    )
    exam_class = forms.ModelChoiceField(queryset=Classroom.objects.none(), required=True)
    questions = forms.ModelMultipleChoiceField(
        queryset=Question.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request:
            self.fields['exam_class'].queryset = Classroom.objects.filter(teacher=request.user)

    class Meta:
        model = Exam
        fields = ['exam_name', 'exam_class', 'exam_date', 'exam_time', 'exam_duration']

   

