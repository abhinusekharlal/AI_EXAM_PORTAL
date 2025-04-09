from django.urls import path
from . import views

app_name = 'results'

urlpatterns = [
    # Teacher views
    path('dashboard/', views.teacher_results_dashboard, name='teacher_dashboard'),
    path('exam/<int:exam_id>/results/', views.exam_results_list, name='exam_results_list'),
    path('review/<int:result_id>/', views.review_flagged_exam, name='review_flagged_exam'),
    path('review/<int:result_id>/process/', views.process_review, name='process_review'),
    path('review/<int:result_id>/frames/', views.review_frames, name='review_frames'),
    path('exam/<int:exam_id>/report/', views.generate_exam_report, name='exam_report'),
    
    # Student views
    path('my-results/', views.student_results, name='student_results'),
    path('detail/<int:result_id>/', views.view_result_detail, name='result_detail'),
]