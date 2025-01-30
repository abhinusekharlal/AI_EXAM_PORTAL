from django.shortcuts import render, redirect, get_object_or_404
from Users.models import User
from .models import Classroom, Exam, Question
from django.contrib.auth.decorators import login_required
from .forms import ClassroomForm, QuestionForm, ExamForm
from django import forms
from datetime import timedelta


class JoinClassForm(forms.Form):
    class_code = forms.CharField(max_length=10, label='Class Code')

# Create your views here.

@login_required
def create_class(request):
    if request.method == 'POST':
        form = ClassroomForm(request.POST)
        if form.is_valid():
            new_class = form.save(commit=False)
            new_class.teacher = request.user
            new_class.save()
            return redirect('Users:dashboard', username=request.user.username)
    else:
        form = ClassroomForm()
    return render(request, 'classroom/create_class.html', {'form': form})

@login_required
def join_class(request):
    if request.method == 'POST':
        form = JoinClassForm(request.POST)
        if form.is_valid():
            class_code = form.cleaned_data['class_code']
            try:
                classroom = Classroom.objects.get(class_code=class_code)
                classroom.students.add(request.user)
                return redirect('Users:dashboard', username=request.user.username)
            except Classroom.DoesNotExist:
                return render(request, 'classroom/join_class.html', {'form': form, 'error': 'Class does not exist'})
    else:
        form = JoinClassForm()
    return render(request, 'classroom/join_class.html', {'form': form})

@login_required
def delete_class(request, class_id):
    classroom = get_object_or_404(Classroom, id=class_id, teacher=request.user)
    if request.method == 'POST':
        classroom.delete()
        return redirect('Users:dashboard', username=request.user.username)

@login_required
def manage_students(request, class_id):
    classroom = get_object_or_404(Classroom, id=class_id, teacher=request.user)
    joined_students = classroom.students.all()
    context = {
        'classroom': classroom,
        'joined_students': joined_students,
    }
    return render(request, 'classroom/manage_students.html', context)

@login_required
def remove_student(request, class_id, student_id):
    classroom = get_object_or_404(Classroom, id=class_id, teacher=request.user)
    student = get_object_or_404(User, id=student_id)
    classroom.students.remove(student)
    return redirect('classroom:manage_students', class_id=class_id)

def view_texams(request):
    return render(request,'classroom/Exam_Schedule.html')

@login_required
def add_exam(request):
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
    classrooms = Classroom.objects.filter(teacher=request.user)
    usr = request.user
    print(request.user.id)
    print(classrooms)
    if request.method == 'POST':
        exam_form = ExamForm(request.POST, request=request)
        question_form = QuestionForm(request.POST)
        if exam_form.is_valid() and question_form.is_valid():
            exam = exam_form.save(commit=False)
            exam.teacher = request.user  # Assuming the Exam model has a teacher field
            exam.save()
            question = question_form.save(commit=False)
            question.exam = exam
            question.save()
            return redirect('classroom:schedule')  # Redirect to a view that lists exams
    else:
        exam_form = ExamForm(request=request)
        question_form = QuestionForm()
    context = {
        'exam_form': exam_form,
        'question_form': question_form,
        'classrooms': classrooms
    }
    return render(request, 'classroom/create_exam.html', context)

def delete_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if request.method == 'POST':
        exam.delete()
        return redirect('classroom:schedule')
    
@login_required
def view_exam(request, exam_id):
    if request.user.user_type != 'student':
        return redirect('Users:access_denied')
    
    exam = get_object_or_404(Exam, id=exam_id)
    exam_time = Exam.objects.get(id=exam_id).exam_time

    questions = Question.objects.filter(exam=exam)
    context = {
        'exam': exam,
        'questions': questions,
        'exam_time': exam_time
    }
    return render(request, 'classroom/exam_interface.html', context)