from django.urls import path, include

urlpatterns = [
    path('exam/',include('exams.urls')),
    path('users/',include('users.urls')),
]
