from django.contrib import admin

from .models import Exam, Question, Submission

admin.site.register(Exam)
admin.site.register(Question)
admin.site.register(Submission)
