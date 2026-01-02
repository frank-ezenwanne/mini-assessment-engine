from django.db import models
import uuid
from django.utils import timezone
from users.models import CustomUser

class Question(models.Model):
    QUESTION_TYPE_CHOICES = (
        ('pattern','pattern'),
        ('mcq','mcq')
    )
    CORRECT_OPTIONS_CHOICES = (
        ('a','a'),
        ('b','b'),
        ('c','c'),
        ('d','d')
    )

    COURSE_OPTIONS = (
        ('mathematics','mathematics'),
        ('physics','physics'),
        ('english','english'),
    )
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)   
    question_text = models.TextField()
    question_type = models.CharField(max_length = 4, choices = QUESTION_TYPE_CHOICES)
    expected_answer = models.CharField(max_length=1, choices = CORRECT_OPTIONS_CHOICES)
    course = models.CharField(max_length=100, choices = COURSE_OPTIONS)


class Exam(models.Model):

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)  
    title = models.CharField(max_length=100)
    course = models.CharField(max_length=100, choices = Question.COURSE_OPTIONS)
    time_created = models.DateTimeField(default=timezone.now)
    time_ended = models.DateTimeField(null=True, blank=True)
    questions = models.ManyToManyField(Question, related_name='exam_questions')
    initiated_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    submission = models.ForeignKey('Submission',null=True, blank=True, on_delete=models.SET_NULL )

class Submission(models.Model):

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)  
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    time_created = models.DateTimeField(default=timezone.now)
    total_questions_answered = models.PositiveIntegerField(default=0)
    answer_1 = models.CharField(max_length=4, null=True,blank=True)
    answer_2 = models.CharField(max_length=4, null=True,blank=True)
    answer_3 = models.CharField(max_length=4, null=True,blank=True)
    answer_4 = models.CharField(max_length=4, null=True,blank=True)
    answer_5 = models.CharField(max_length=4, null=True,blank=True)
    answer_6 = models.CharField(max_length=4, null=True,blank=True)
    answer_7 = models.CharField(max_length=4, null=True,blank=True)
    answer_8 = models.CharField(max_length=4, null=True,blank=True)
    answer_9 = models.CharField(max_length=4, null=True,blank=True)
    answer_10 = models.CharField(max_length=4, null=True,blank=True)
    answered_questions = models.JSONField(null=True,blank=True) #mapping of question id to qnum

