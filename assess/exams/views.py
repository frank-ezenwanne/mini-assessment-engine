from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from .serializers import ExamStartSerializer,ExamResponseSerializer, AnswerQuestionSerializer, \
    SelectQuestionSerializer, BasicExamSerializer,CourseSerializer
from .models import Exam, Question, Submission
from datetime import datetime
from utils.response_format import server_error, success_response, error_response
from utils.result_grade import grade_exam_logic
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist, ValidationError
import time

class StartExamView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ["POST"]
    serializer_class = ExamStartSerializer

    def prepare_response(self, exam, selected_answers_map):
        try:
            first_question = Question.objects.get(id=exam.question_map[1])
        except ObjectDoesNotExist:
            raise ValidationError('Question could not be loaded !')

        response_data = ExamResponseSerializer(
            exam = exam.id,
            time_started = exam.time_started,
            question = first_question,
            selected_answers_map = selected_answers_map,
            title = exam.title
        ).data

        return success_response(msg='Exam loaded', data=response_data )
    
    def handle_ongoing_exam(self, exam):
        if time.time() - exam.time_ended.timestamp() >= Exam.EXAM_DURATION:
            exam.ended == True
            exam.save()
            submission = exam.submission
            results_map, final_score = grade_exam_logic(exam, submission.already_scored)
            return success_response(
                    data = {
                        'results_map':results_map,
                        'final_score':final_score
                    }
                )
        selected_answers_map = exam.submission.selected_answers_map
        return self.prepare_response(exam, selected_answers_map) #if not ended..push to the user


    @transaction.atomic #so exam n submission instances are created all or none !
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception = True)
        exam = serializer.validated_data.get('exam')

        if not exam:
            course = serializer.validated_data.get('course')
            ongoing_exam = Exam.objects.filter(course = course, ended=False, submission__student = request.user).first() #check if there is an ongoing exam
            if ongoing_exam:
                return self.handle_ongoing_exam(ongoing_exam)

            max_questions = Exam.MAX_QUESTION_NUMBER
            questions = Question.objects.filter(
                course = course
            )[:max_questions] #apply LIMIT depending on max questions in SQL, and without order to allow for some randomness in question ordering across users

            if questions.count() < max_questions:
                return server_error(msg=_(f'{course.capitalize()} exam questions not yet available.'))
            
            question_map = {serial+1 : question.id for serial, question in enumerate(questions)}
            empty_answers_map = {serial:'' for serial in range(1,max_questions + 1)}

            exam = Exam.objects.create(
                title = f'{course.capitalize()}_Exam_{datetime.now().year}',
                course = course,
                initiated_by = request.user,
                question_map = question_map,
                expected_answers_map = empty_answers_map
            )
        
            Submission.objects.create(
                exam = exam,
                student = request.user,
                selected_answers_map = empty_answers_map
            )

            return self.prepare_response(exam, empty_answers_map)

        else:
            if exam.time_ended or exam.ended == True:
                return error_response(msg='This Exam is already ended..Retake')
            return self.handle_ongoing_exam(ongoing_exam) 

           

class AnswerQuestionView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ["POST"]
    serializer_class = AnswerQuestionSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception = True)
        question_number = serializer.validated_data.get('question_number')
        answer = serializer.validated_data.get('answer')
        submission = serializer.validated_data.get('submission')
        submission.selected_answers_map[question_number] = answer
        submission.save()
        return success_response(msg = 'submitted', data = submission.selected_answers_map)


class SelectQuestionView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ["POST"]
    serializer_class = SelectQuestionSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception = True)
        question_number = serializer.validated_data.get('question_number')
        selected_answers_map = serializer.validated_data.get('selected_answers_map')
        question = serializer.validated_data.get('question')
        return success_response(data = {
            'question_number' : question_number,
            'selected_answers_map' : selected_answers_map,
            'question' : question
        })


class FetchExams(GenericAPIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ["GET"]
    serializer_class = CourseSerializer
    def post(self, request, course, *args, **kwargs):
        serializer = self.get_serializer(data={'course':course})
        serializer.is_valid(raise_exception = True)
        course = serializer.validated_data.get('course')
        exams = Exam.objects.filter(course = course, submission__student = request.user)



class TerminateGradeExamView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ["POST"]
    serializer_class = BasicExamSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception = True)
        exam = serializer.validated_data.get('exam')
        exam.ended = True
        exam.save()
        submission = exam.submission
        results_map, final_score = grade_exam_logic(exam, submission.already_scored)
        return success_response(
            data = {
                'results_map':results_map,
                'final_score':final_score
            }
        )





            


        






        
        


        

