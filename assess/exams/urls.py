from django.urls import path
from .views import StartExamView, AnswerQuestionView, SelectQuestionView, FetchExamsHistoryView,\
ExamPerformanceView, TerminateGradeExamView,UploadCSVQuestions

urlpatterns = [
    path('start-exam', StartExamView.as_view(), name='start-exam'),
    path('answer-question', AnswerQuestionView.as_view(), name='answer-question'),
    path('select-question', SelectQuestionView.as_view(), name='select-question'),
    path('fetch-exams-history/<str:course>/', FetchExamsHistoryView.as_view(), name='fetch-exams-history'), #slash added because of pagination
    path('exam-performance', ExamPerformanceView.as_view(), name='exam-performance'),
    path('terminate-and-grade', TerminateGradeExamView.as_view(), name='terminate-and-grade'),
    path('admin/upload-csv-questions', UploadCSVQuestions.as_view(), name='upload-csv-questions')
]