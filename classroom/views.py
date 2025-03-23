from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from Users.models import User
from .models import Classroom, Exam, Question
from django.contrib.auth.decorators import login_required
from .forms import ClassroomForm, QuestionForm, ExamForm
from django import forms
from django.utils import timezone
from datetime import timedelta, datetime
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
import json
# Import the ExamSession model
from monitoring.models import ExamSession
# Import the ExamResult model
from results.models import ExamResult

import threading

from django.http import StreamingHttpResponse
import cv2

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
    exams = Exam.objects.filter(teacher=request.user)
    return render(request,'classroom/Exam_Schedule.html',{'exams':exams})

@login_required
def add_exam(request):
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
    
    if request.method == 'POST':
        exam_form = ExamForm(request.POST, request=request)
        questions_data = []
        
        # Collect all question forms data
        i = 0
        # while f'question_text_{i}' in request.POST:
        while f'question_{i}-question_text' in request.POST:
            question_data = {
                # 'question_text': request.POST.get(f'question_text_{i}'),
                # 'option1': request.POST.get(f'option1_{i}'),
                # 'option2': request.POST.get(f'option2_{i}'),
                # 'option3': request.POST.get(f'option3_{i}'),
                # 'option4': request.POST.get(f'option4_{i}'),
                # 'correct_option': request.POST.get(f'correct_option_{i}'),
                'question_text': request.POST.get(f'question_{i}-question_text'),
                'option1': request.POST.get(f'question_{i}-option1'),
                'option2': request.POST.get(f'question_{i}-option2'),
                'option3': request.POST.get(f'question_{i}-option3'),
                'option4': request.POST.get(f'question_{i}-option4'),
                'correct_option': request.POST.get(f'question_{i}-correct_option'),
            }
            questions_data.append(question_data)
            i += 1

        if exam_form.is_valid():
            exam = exam_form.save(commit=False)
            exam.teacher = request.user
            exam.status = 'published'  # Set a default status value
            exam.save()

            # Save all questions
            print(questions_data)
            for question_data in questions_data:
                question_form = QuestionForm(question_data)
                # print(question_data)
                if question_form.is_valid():
                    question = question_form.save(commit=False)
                    question.exam = exam
                    question.save()

            return redirect('classroom:schedule')
    else:
        exam_form = ExamForm(request=request)
    
    return render(request, 'classroom/create_exam.html', {
        'exam_form': exam_form
    })

@login_required
def add_question_form(request):
    """View to return a new question form via HTMX"""
    try:
        question_count = int(request.GET.get('count', 0))
    except ValueError:
        question_count = 0
        
    form = QuestionForm(prefix=f'question_{question_count}')
    context = {
        'form': form,
        'number': question_count + 1,
        'prefix': f'question_{question_count}'
    }
    
    print(f"Adding question form {question_count + 1}")  # Debug print
    return render(request, 'classroom/partials/question_form.html', context)

@login_required
def delete_question(request):
    """Handle question deletion via HTMX"""
    if request.method == 'DELETE':
        # Since we're just removing the form element, no need to actually delete from DB
        return HttpResponse(status=200)
    return HttpResponseBadRequest()

def delete_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if request.method == 'POST':
        exam.delete()
        return redirect('classroom:schedule')

@login_required
def edit_exam(request,exam_id):
    if request.user.user_type != 'teacher':
        return redirect('Users:access_denied')
    
    exam = get_object_or_404(Exam, id=exam_id)
    questions = Question.objects.filter(exam=exam).order_by('id')
    
    if request.method == 'POST':
        exam_form = ExamForm(request.POST, instance=exam, request=request)
        questions_data = []
        
        # Collect all question forms data
        i = 0
        while f'question_{i}-question_text' in request.POST:
            question_data = {
                'question_text': request.POST.get(f'question_{i}-question_text'),
                'option1': request.POST.get(f'question_{i}-option1'),
                'option2': request.POST.get(f'question_{i}-option2'),
                'option3': request.POST.get(f'question_{i}-option3'),
                'option4': request.POST.get(f'question_{i}-option4'),
                'correct_option': request.POST.get(f'question_{i}-correct_option'),
            }
            questions_data.append(question_data)
            i += 1

        if exam_form.is_valid():
            exam = exam_form.save(commit=False)
            exam.teacher = request.user
            exam.status = 'published'  # Ensure status is set when editing
            exam.save()

            # Save all questions
            for question_data in questions_data:
                question_form = QuestionForm(question_data)
                if question_form.is_valid():
                    question = question_form.save(commit=False)
                    question.exam = exam
                    question.save()

            return redirect('classroom:schedule')
    else:
        exam_form = ExamForm(instance=exam, request=request)
    
    return render(request, 'classroom/edit_exam.html', {
        'exam_form': exam_form,
        'exam': exam
    })

@login_required
def view_exam(request, exam_id):
    if request.user.user_type != 'student':
        return redirect('Users:access_denied')
    
    exam = get_object_or_404(Exam, id=exam_id)
    questions = Question.objects.filter(exam=exam).order_by('id')
    
    # Calculate duration in minutes
    duration_minutes = int(exam.exam_duration.total_seconds() / 60)
    
    # Get current time using Django's timezone
    current_time = timezone.now()
    
    context = {
        'exam': exam,
        'questions': questions,
        'duration_minutes': duration_minutes,
        'total_questions': questions.count(),
        'csrf_token': request.COOKIES.get('csrftoken'),
        'start_time': current_time.isoformat(),
    }
    
    # Set exam session data in Django session
    request.session[f'exam_{exam_id}_started'] = True
    request.session[f'exam_{exam_id}_start_time'] = current_time.isoformat()
    
    # Create or get an ExamSession record for monitoring
    exam_session, created = ExamSession.objects.get_or_create(
        exam=exam,
        student=request.user,
        is_active=True,
        defaults={
            'started_at': current_time,
            'last_activity': current_time
        }
    )
    
    return render(request, 'classroom/exam_interface.html', context)

@login_required
def submit_exam(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            exam_id = data.get('examId')
            answers = data.get('answers', {})
            
            if not exam_id:
                return JsonResponse({'success': False, 'error': 'Missing exam ID'}, status=400)
            
            exam = get_object_or_404(Exam, id=exam_id)
            
            # Try to get the start time from session
            start_time_str = request.session.get(f'exam_{exam_id}_start_time')
            start_time = None
            if start_time_str:
                try:
                    start_time = datetime.fromisoformat(start_time_str)
                except (ValueError, TypeError):
                    pass
            
            # Get or mark inactive the exam session
            try:
                exam_session = ExamSession.objects.get(
                    exam_id=exam_id,
                    student=request.user,
                    is_active=True
                )
                exam_session.is_active = False
                exam_session.save()
                
                # Use the session start time if available
                if not start_time and exam_session.started_at:
                    start_time = exam_session.started_at
                    
            except ExamSession.DoesNotExist:
                pass  # No active session found, which is unexpected but we can continue
            
            # Create permanent exam result record
            exam_result = ExamResult.create_from_submission(
                student=request.user,
                exam=exam,
                answers=answers,
                start_time=start_time
            )
            
            # Store the result ID and score in the session for the completion page
            request.session[f'exam_{exam_id}_result_id'] = str(exam_result.id)
            request.session[f'exam_{exam_id}_score'] = exam_result.score
            
            return JsonResponse({
                'success': True,
                'score': exam_result.score,
                'redirect_url': reverse('classroom:exam_completed')
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

@login_required
def exam_completed(request):
@login_required
def exam_completed(request):
    try:
        # First try to get the result directly if we have the ID
        result_id = None
        exam_id = None
        
        # Find the most recent exam result ID from the session
        for key in request.session.keys():
            if key.endswith('_result_id'):
                exam_id = key.split('_')[1]
                result_id = request.session.get(key)
                # Clear the session key after retrieving it
                del request.session[key]
                break
        
        if result_id:
            try:
                # Get the stored result and ensure it belongs to this student
                exam_result = ExamResult.objects.select_related('exam').get(
                    id=result_id, 
                    student=request.user
                )
                
                context = {
                    'exam': exam_result.exam,
                    'score': exam_result.score,
                    'completion_time': exam_result.completion_time,
                    'correct_answers': exam_result.correct_answers,
                    'total_questions': exam_result.total_questions,
                    'duration': exam_result.duration_in_minutes,
                    'status': exam_result.status,
                    'result': exam_result,
                }
                
                return render(request, 'classroom/exam_completed.html', context)
                
            except ExamResult.DoesNotExist:
                pass

        # Fallback to the most recent completed exam session
        last_exam_session = ExamSession.objects.filter(
            student=request.user,
            is_active=False
        ).select_related('exam').order_by('-last_activity').first()
        
        if last_exam_session:
            exam = last_exam_session.exam
            
            # Try to find a result for this exam
            try:
                exam_result = ExamResult.objects.get(
                    student=request.user, 
                    exam=exam
                )
                
                context = {
                    'exam': exam_result.exam,
                    'score': exam_result.score,
                    'completion_time': exam_result.completion_time,
                    'correct_answers': exam_result.correct_answers,
                    'total_questions': exam_result.total_questions,
                    'duration': exam_result.duration_in_minutes,
                    'status': exam_result.status,
                    'result': exam_result,
                }
                
                return render(request, 'classroom/exam_completed.html', context)
                
            except ExamResult.DoesNotExist:
                # If no result exists, use session data
                score = request.session.get(f'exam_{exam.id}_score', 0)
                completion_time = last_exam_session.last_activity
                
                context = {
                    'exam': exam,
                    'score': score,
                    'completion_time': completion_time
                }
                
                return render(request, 'classroom/exam_completed.html', context)
                
    except Exception as e:
        # Log the exception
        print(f"Error in exam_completed view: {str(e)}")
    
    # If we get here, either there's no completed exam or an error occurred
    return render(request, 'classroom/exam_completed.html', {
        'generic_completion': True
    })


# Open video source
camera = cv2.VideoCapture(0)
frame_lock = threading.Lock()
current_frame = None

# Capture frames in a background thread
def capture_frames():
    global current_frame
    while True:
        success, frame = camera.read()
        if not success:
            break
        with frame_lock:
            current_frame = frame

# Start the capture thread
threading.Thread(target=capture_frames, daemon=True).start()

# Frame generator for streaming
def generate_frames():
    while True:
        with frame_lock:
            if current_frame is None:
                continue
            _, buffer = cv2.imencode('.jpg', current_frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# Streaming views
def video_feed(request):
    return StreamingHttpResponse(generate_frames(), content_type='multipart/x-mixed-replace; boundary=frame')

def admin_feed(request):
    return StreamingHttpResponse(generate_frames(), content_type='multipart/x-mixed-replace; boundary=frame')