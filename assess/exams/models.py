from django.db import models
import uuid
from django.utils import timezone
from users.models import CustomUser
from rest_framework.serializers import ValidationError 

class Question(models.Model):

    PATTERN = 'pattern'
    MCQ = 'mcq'

    QUESTION_TYPE_CHOICES = (
        (PATTERN, PATTERN),
        (MCQ, MCQ)
    )

    MATHS = 'maths'
    PHYSICS = 'physics'
    ENGLISH = 'english'

    COURSE_OPTIONS = (
        (MATHS, MATHS),
        (PHYSICS, PHYSICS),
        (ENGLISH, ENGLISH),
    )


    OPTION_A = 'a'
    OPTION_B = 'b'
    OPTION_C = 'c'
    OPTION_D = 'd'

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)   
    question_text = models.TextField()
    question_type = models.CharField(max_length = 7, choices = QUESTION_TYPE_CHOICES)
    expected_answer = models.CharField(max_length = 4) #in case of pattern questions
    course = models.CharField(max_length=100, choices = COURSE_OPTIONS)
    option_a = models.CharField(max_length=255,null=True,blank=True)
    option_b = models.CharField(max_length=255,null=True,blank=True)
    option_c = models.CharField(max_length=255,null=True,blank=True)
    option_d = models.CharField(max_length=255,null=True,blank=True)

    def clean(self):
        if self.question_type == self.PATTERN and len(self.expected_answer) != 4 or self.question_type == self.PATTERN and not all(char in (self.OPTION_A,self.OPTION_B,self.OPTION_C,self.OPTION_D) for char in self.expected_answer) :
            raise ValidationError(f'Answer string of 4 char length having letters {self.OPTION_A,self.OPTION_B,self.OPTION_C,self.OPTION_D} must be provided for a pattern-based question')
        
        if self.question_type == self.MCQ and len(self.expected_answer) != 1 or self.question_type == self.MCQ and self.expected_answer not in (self.OPTION_A,self.OPTION_B,self.OPTION_C,self.OPTION_D):
            raise ValidationError(f'Answer string of 1 char length having 1 of {self.OPTION_A, self.OPTION_B, self.OPTION_C,self.OPTION_D} must be provided for an mcq-based question')

    def save(self,*args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class Exam(models.Model):

    EXAM_DURATION = 180 #seconds
    MAX_QUESTION_NUMBER = 10

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)  
    title = models.CharField(max_length=100)
    course = models.CharField(max_length=100, choices = Question.COURSE_OPTIONS)
    time_started = models.DateTimeField(default=timezone.now)
    time_ended = models.DateTimeField(null=True, blank=True)
    ended = models.BooleanField(default=False)
    question_map = models.JSONField(null=True,blank=True) #mapping of question qnum to id
    initiated_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        if self._state.adding == False: #if it is updated not being created
            old_instance = Exam.objects.get(pk=self.pk)
            if old_instance.ended == False and self.ended == True:
                self.time_ended = timezone.now()
        super().save(*args, **kwargs)

class Submission(models.Model):

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)  
    exam = models.OneToOneField('Exam', on_delete = models.CASCADE )
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    time_created = models.DateTimeField(default=timezone.now)
    total_questions_answered = models.PositiveIntegerField(default=0)
    selected_answers = models.JSONField(null=True,blank=True) #mapping of question num to answer

