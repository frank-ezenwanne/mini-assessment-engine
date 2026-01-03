from rest_framework import serializers
from rest_framework.serializers import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import Question, Exam
from django.core.exceptions import ObjectDoesNotExist

class ExamStartSerializer(serializers.Serializer):
    course = serializers.ChoiceField(choices = Question.COURSE_OPTIONS, required = False)
    exam_id = serializers.UUIDField(required = False)

    def validate(self, data):
        data=super().validate(data)
        if all(value in ['None', ''] for value in data.values()):
            raise ValidationError('All fields cannot be empty')
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
    
    def to_representation(self, instance):
        data = super().to_representation(instance)

    
class ExamSessionSerializer(serializers.Serializer):
    exam = serializers.UUIDField(read_only=True)
    time_started = serializers.DateTimeField(read_only=True)
    question = DisplayExamQuestionSerializer(read_only=True)
    selected_answers = serializers.JSONField(read_only=True)

    def validate(self, data):
        data =  super().validate(data)
        exam = data.get('exam')
        try:
            exam = Exam.objects.select_related('submission').get(id=exam)
        except ObjectDoesNotExist:
            raise ValidationError('Exam not found')
        data['exam'] = exam
        return data

    
class AnswerQuestionSerializer(serializers.Serializer):
    exam = serializers.UUIDField(read_only=True)
    answer = serializers.CharField(max_length = 4) #in case of pattern questions
    question_number = serializers.IntegerField(min_value = 1, max_value = Exam.MAX_QUESTION_NUMBER)

    def validate(self, data):
        data = super().validate(data)
        exam = data.get('exam')
        try:
            exam = Exam.objects.select_related('submission').get(id=exam)
        except ObjectDoesNotExist:
            raise ValidationError('Exam not found')
        data['exam'] = exam

        question_id = exam.question_map[data.get('question_number')]

        try:
            question = Question.objects.get(id = question_id)
        except ObjectDoesNotExist:
            raise ValidationError('Question not found')
        
        question_type = question.question_type
        data['question'] = question
        
        if question_type == Question.PATTERN and len(data['answer']) != 4 or question_type == Question.PATTERN and not all(char in (Question.OPTION_A,Question.OPTION_B,Question.OPTION_C,Question.OPTION_D) for char in data['answer']) :
            raise ValidationError(f'Answer of 4 char length having letters {Question.OPTION_A,Question.OPTION_B,Question.OPTION_C,Question.OPTION_D} must be provided for a pattern-based question')
        
        if question_type == Question.MCQ and len(data['answer']) != 1 or question_type == Question.MCQ and data['answer'] not in (Question.OPTION_A,Question.OPTION_B,Question.OPTION_C,Question.OPTION_D):
            raise ValidationError(f'Answer of 1 char length having 1 of {Question.OPTION_A, Question.OPTION_B, Question.OPTION_C,Question.OPTION_D} must be provided for an mcq-based question')

        return data

