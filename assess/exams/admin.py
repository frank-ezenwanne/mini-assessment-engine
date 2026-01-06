from django.contrib import admin

from .models import Exam, Question, Submission


@admin.register(Exam)
class AdminExam(admin.ModelAdmin):
    ordering = ['-time_started']

@admin.register(Question)
class AdminQuestion(admin.ModelAdmin):
    ordering = ['-timestamp']

@admin.register(Submission)
class AdminSubission(admin.ModelAdmin):
    ordering = ['-time_created']