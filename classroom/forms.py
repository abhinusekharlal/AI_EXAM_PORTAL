from django import forms
from .models import Classroom

class ClassroomForm(forms.ModelForm):
    class Meta:
        model = Classroom
        fields = ['class_name', 'class_description']


class JoinClassForm(forms.Form):
    class_code = forms.CharField(max_length=10, required=True)