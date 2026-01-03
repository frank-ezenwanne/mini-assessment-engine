from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .serializers import ExamStartSerializer,ExamSessionSerializer, AnswerQuestionSerializer
from .models import Exam, Question, Submission
from datetime import datetime
from utils.response_format import server_error, success_response, error_response
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist, ValidationError
import time
from django.utils import timezone

class StartExamView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ["POST"]

    def prepare_response(exam, selected_answers):
        try:
            first_question = Question.objects.get(id=exam.question_map[1])
        except ObjectDoesNotExist:
            raise ValidationError('Question could not be loaded !')

        response_data = ExamSessionSerializer(
            exam_id = exam.id,
            time_started = exam.time_started,
            question = first_question,
            selected_answers = selected_answers
        ).data

        return success_response(msg='Exam Started', data=response_data )

    @transaction.atomic #so exam n submission instances are created all or none !
    def post(self, request, *args, **kwargs):
        serializer = ExamStartSerializer(data=request.data)
        serializer.is_valid(raise_exception = True)
        exam = serializer.validated_data.get('exam')

        if not exam:
            max_questions = Exam.MAX_QUESTION_NUMBER
            course = serializer.validated_data.get('course')

            questions = Question.objects.filter(
                course = course
            )[:max_questions] #apply LIMIT depending on max questions in SQL, and without order to allow for some randomness in question ordering across users

            if questions.count() < max_questions:
                return server_error(msg=_(f'{course.capitalize()} exam questions not yet available.'))
            
            question_map = {serial+1 : question.id for serial, question in enumerate(questions)}
            exam = Exam.objects.create(
                title = f'{course.capitalize()}_Exam_{datetime.now().year}',
                course = course,
                initiated_by = request.user,
                question_map = question_map
            )

            selected_answers = {serial:'' for serial in range(1,max_questions + 1)}
            Submission.objects.create(
                exam = exam,
                student = request.user,
                selected_answers = selected_answers
            )

            return self.prepare_response(exam, selected_answers)

        else:
            selected_answers = exam.submission.selected_answers
            if time.time() - exam.time_ended.timestamp() >= Exam.EXAM_DURATION:
                exam.ended == True
                exam.save()
            if exam.time_ended or exam.ended == True:
                return error_response(msg='This Exam is already ended')
            
            return self.prepare_response(exam, selected_answers)
           

class AnswerQuestionView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ["POST"]

    def post(self, request, *args, **kwargs):
        serializer = AnswerQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception = True)
        question = serializer.validated_data['question']
        question_number = serializer.validated_data['question_number']






        
        


        

