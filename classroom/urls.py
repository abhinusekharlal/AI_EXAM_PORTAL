from django.urls import path
from . import views
from Users.views import access_denied
from .views import video_feed, admin_feed

app_name = 'classroom'

urlpatterns = [
    path('classroom/', views.view_texams, name='schedule'),
    path('classroom/create', views.create_class, name='create_class'),
    path('classroom/join', views.join_class, name='join_class'),
    path('classroom/addexam', views.add_exam, name='add_exam'),
    path('classroom/edit_exam/<int:exam_id>/', views.edit_exam, name='edit_exam'),
    path('classroom/exam/<int:exam_id>/', views.view_exam, name='view_exam'),
    path('classroom/delete_exam/<int:exam_id>/', views.delete_exam, name='delete_exam'),
    path('classroom/delete/<uuid:class_id>/', views.delete_class, name='delete_class'),
    path('classroom/manage_students/<uuid:class_id>/', views.manage_students, name='manage_students'),
    path('classroom/remove_student/<uuid:class_id>/<uuid:student_id>/', views.remove_student, name='remove_student'),
    path('classroom/add-question-form/', views.add_question_form, name='add_question_form'),
    path('classroom/delete-question/', views.delete_question, name='delete_question'),
    path('classroom/submit-exam/', views.submit_exam, name='submit_exam'),
    path('classroom/exam-completed/', views.exam_completed, name='exam_completed'),
    #video streaming
    path('classroom/video_feed', video_feed, name='video_feed'),
    path('classroom/admin_feed', admin_feed, name='admin_feed'),
]
