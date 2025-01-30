from django.contrib import admin
from .models import Classroom, Exam, Question

# Register your models here.
admin.site.register(Classroom)
admin.site.register(Exam)
admin.site.register(Question)