from rest_framework import serializers
from rest_framework.serializers import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import Question, Exam
from django.core.exceptions import ObjectDoesNotExist
from utils.exam_perms import get_exam_with_perm


#REQUEST SERIALIZERS
class ExamStartSerializer(serializers.Serializer):
    course = serializers.ChoiceField(choices = Question.COURSE_OPTIONS, required = False)
    exam = serializers.UUIDField(required = False)

    def validate(self, data):
        if all(value in ['None', ''] for value in data.values()):
            raise ValidationError('All fields cannot be empty')
        if data.get('exam'):
            request = self.context.get('request')
            exam = get_exam_with_perm(data['exam'], request.user)
            data['exam'] = exam
        return data

class DisplayExamQuestionSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Question
        fields = ('question_text','question_type','course','option_a','option_b','option_c','option_d')

    def get_fields(self): #make all fields read only to prevent writes via incoming requests
        fields = super().get_fields()
        for field in fields.values():
            field.read_only = True
        return fields
    

class AnswerQuestionSerializer(serializers.Serializer):
    exam = serializers.UUIDField()
    answer = serializers.CharField(max_length = 4) #in case of pattern questions
    question_number = serializers.IntegerField(min_value = 1, max_value = Exam.MAX_QUESTION_NUMBER)

    def validate(self, data):
        request = self.context.get('request')
        exam = get_exam_with_perm(data['exam'], request.user)
        
        data['exam'] = exam

        question_number = str(data.get('question_number'))

        question_id = exam.question_map[question_number]

        try:
            question = Question.objects.get(id = question_id)
        except ObjectDoesNotExist:
            raise ValidationError('Question not found')
        
        question_type = question.question_type
        data['submission_id'] = exam.submission.id
        
        if question_type == Question.PATTERN and len(data['answer']) != 4 or question_type == Question.PATTERN and not all(char in (Question.OPTION_A,Question.OPTION_B,Question.OPTION_C,Question.OPTION_D) for char in data['answer']) :
            raise ValidationError(f'Answer of 4 char length having letters {Question.OPTION_A,Question.OPTION_B,Question.OPTION_C,Question.OPTION_D} must be provided for a pattern-based question')
        
        if question_type == Question.MCQ and len(data['answer']) != 1 or question_type == Question.MCQ and data['answer'] not in (Question.OPTION_A,Question.OPTION_B,Question.OPTION_C,Question.OPTION_D):
            raise ValidationError(f'Answer of 1 char length having 1 of {Question.OPTION_A, Question.OPTION_B, Question.OPTION_C,Question.OPTION_D} must be provided for an mcq-based question')

        return data

class SelectQuestionSerializer(serializers.Serializer):
    exam = serializers.UUIDField()
    question_number = serializers.IntegerField(min_value = 1, max_value = Exam.MAX_QUESTION_NUMBER)

    def validate(self, data):

        request = self.context.get('request')
        exam = get_exam_with_perm(data['exam'], request.user)

        question_number = str(data.get('question_number'))

        question_id = exam.question_map[question_number]

        try:
            question = Question.objects.get(id = question_id)
        except ObjectDoesNotExist:
            raise ValidationError('Question not found')
        
        data['question'] = DisplayExamQuestionSerializer(question).data
        data['selected_answers_map'] = exam.submission.selected_answers_map
        data['exam'] = exam

        return data


class BasicExamSerializer(serializers.Serializer):
    exam = serializers.UUIDField()

    def validate(self, data):
        request = self.context.get('request')
        exam = get_exam_with_perm(data['exam'], request.user)
        
        data['exam'] = exam
        return data

class CourseSerializer(serializers.Serializer):
    course = serializers.ChoiceField(choices = Question.COURSE_OPTIONS)



class CSVUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        if not value.name.endswith('.csv'):
            raise ValidationError('Pls Upload a CSV file !')
        return value
    



#RESPONSE SERIALIZERS
class BaseExamSessionSerializer(serializers.Serializer): 
    """
    base serializer to be used by every view involved
      in the exam session i.e selecting/answering questions/terminating exam
      not fetching results or viewing history

      The views in question should always tell us whether the exam has ended or not, e.g due to a timeout
      This is necessary for the frontend to React accordingly
    """
    exam_ended = serializers.BooleanField(required = True)


class ExamResponseSerializer(BaseExamSessionSerializer):
    exam = serializers.UUIDField()
    title = serializers.CharField()
    time_started = serializers.DateTimeField()
    question = DisplayExamQuestionSerializer()
    question_number = serializers.CharField()
    selected_answers_map = serializers.DictField(child=serializers.CharField())

class AnswerQuestionResponseSerializer(BaseExamSessionSerializer):
    selected_answers_map = serializers.DictField(child=serializers.CharField())

class SelectQuestionResponseSerializer(BaseExamSessionSerializer):
    question_number = serializers.CharField()  
    selected_answers_map = serializers.DictField(child=serializers.CharField())
    question = DisplayExamQuestionSerializer()   


class ExamHistoryResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exam
        fields = ('id','title','course','time_started','time_ended','ended')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.submission.already_scored == True:
            data['final_score'] = instance.final_score
        return data
    
class ResultChildSerializer(serializers.Serializer):
    question = DisplayExamQuestionSerializer()
    selected_answer = serializers.CharField()
    is_correct = serializers.BooleanField()
    expected_answer = serializers.CharField()

class ResultResponseSerializer(BaseExamSessionSerializer):
    results_map = serializers.DictField(child=ResultChildSerializer(),help_text="A mapping where the key is the string rep of the Question Number.")
    final_score = serializers.CharField()


    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['final_score'] = f"{data['final_score']}%"
        return data