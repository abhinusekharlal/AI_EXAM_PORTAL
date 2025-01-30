from django.urls import path
from . import views
from Users.views import access_denied

app_name = 'classroom'

urlpatterns = [
    path('classroom/', views.view_texams, name='schedule'),
    path('classroom/create', views.create_class, name='create_class'),
    path('classroom/join', views.join_class, name='join_class'),
    path('classroom/addexam', views.add_exam, name='add_exam'),
    path('classroom/exam/<int:exam_id>/', views.view_exam, name='view_exam'),
    path('classroom/delete_exam/<int:exam_id>/', views.delete_exam, name='delete_exam'),
    path('classroom/delete/<uuid:class_id>/', views.delete_class, name='delete_class'),
    path('classroom/manage_students/<uuid:class_id>/', views.manage_students, name='manage_students'),
    path('classroom/remove_student/<uuid:class_id>/<uuid:student_id>/', views.remove_student, name='remove_student'),
]
