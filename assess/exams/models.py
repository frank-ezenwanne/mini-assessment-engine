from django.db import models
import uuid
from django.utils import timezone
from users.models import CustomUser
from rest_framework.exceptions import ValidationError
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, UniqueConstraint

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
    timestamp = models.DateTimeField(default = timezone.now)

    def clean(self):
        if self.question_type == self.PATTERN and len(self.expected_answer) != 4 or self.question_type == self.PATTERN and not all(char in (self.OPTION_A,self.OPTION_B,self.OPTION_C,self.OPTION_D) for char in self.expected_answer) :
            raise ValidationError(f'Expected Answer string of 4 char length having letters {self.OPTION_A,self.OPTION_B,self.OPTION_C,self.OPTION_D} must be provided for a pattern-based question')
        
        if self.question_type == self.MCQ and len(self.expected_answer) != 1 or self.question_type == self.MCQ and self.expected_answer not in (self.OPTION_A,self.OPTION_B,self.OPTION_C,self.OPTION_D):
            raise ValidationError(f'Expected Answer string of 1 char length having 1 of {self.OPTION_A, self.OPTION_B, self.OPTION_C,self.OPTION_D} must be provided for an mcq-based question')

    def save(self,*args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.course}__{self.question_type}_with_id_{self.id}'

class Exam(models.Model):

    
    MAX_QUESTION_NUMBER = 6 #this settin will change the max questions to be used for any exam
    EXAM_DURATION = MAX_QUESTION_NUMBER * 30 #seconds..30 sec per question 

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)  
    title = models.CharField(max_length=100)
    course = models.CharField(max_length=100, choices = Question.COURSE_OPTIONS)
    time_started = models.DateTimeField(default=timezone.now)
    time_ended = models.DateTimeField(null=True, blank=True)
    ended = models.BooleanField(default=False)
    question_map = models.JSONField(null=True,blank=True) #mapping of question num to id
    initiated_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    class Meta: #this constraint will prevent multiple exams spawning for one user..works in case the select for update block in the view does not hold back any rows i.e no active rows means multiple exams can be created
        constraints = [
            UniqueConstraint(
                fields=["course", "initiated_by"],
                condition=Q(ended=False),
                name="just_one_active_exam_per_course_per_student"
            )
        ]


    def clean(self):
        question_map = self.question_map #for the JSON field
        for key in question_map:
            try:
                qnum = int(key)
            except ValueError:
                raise ValidationError('Question map must be a mapping of question number to uuid')

            if not 1 <= qnum <= self.MAX_QUESTION_NUMBER:
                raise ValidationError('Question map must be a mapping of question number to uuid')
            try:
                uuid.UUID(str(question_map[key]))
                Question.objects.get(id=question_map[key])
            except (ValueError, TypeError, AttributeError):
                raise ValidationError('The string the question number maps to must be a valid UUID')
            except ObjectDoesNotExist:
                raise ValidationError('The question id inserted must point to a valid question ID in the record')


    def save(self, *args, **kwargs):
        if self._state.adding == False: #if it is updated not being created
            old_instance = Exam.objects.get(pk=self.pk)
            if old_instance.ended == False and self.ended == True:
                self.time_ended = timezone.now()
            
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.title}_with_id_{self.id}_initiated_by_{self.initiated_by.first_name}_for_{self.submission.student.first_name}'



class Submission(models.Model):

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)  
    exam = models.OneToOneField('Exam', on_delete = models.CASCADE )
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    time_created = models.DateTimeField(default=timezone.now)
    time_scored = models.DateTimeField(null = True, blank = True)
    already_scored = models.BooleanField(default = False)
    final_score = models.FloatField(default=0) #questions answered correctly
    selected_answers_map = models.JSONField(null=True,blank=True) #mapping of question num to answer


    def clean(self):
        selected_answers_map = self.selected_answers_map #for the JSON field
        for key in selected_answers_map:
            try:
                qnum = int(key)
            except ValueError:
                raise ValidationError('Question map must be a mapping of question number to uuid')
            
            if not 1 <= qnum <= self.exam.MAX_QUESTION_NUMBER or type(selected_answers_map[key]) != str:
                raise ValidationError('answer map must be a mapping of question number to option selections [str]')
        
    def save(self, *args, **kwargs):         
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Submission_for_Exam_for_{self.student.first_name}'