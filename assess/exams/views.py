from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers
from .serializers import ExamStartSerializer, AnswerQuestionSerializer, SelectQuestionSerializer,\
      BasicExamSerializer,CourseSerializer, CSVUploadSerializer,BaseExamSessionSerializer,\
        ExamResponseSerializer,ExamHistorySerializer,AnswerQuestionResponseSerializer
from .models import Exam, Question, Submission
from datetime import datetime
from utils.response_format import server_error, success_response, error_response
from utils.result_grade import grade_exam_logic
from utils.pagination import CustomPagination
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist, ValidationError
import time
import io
import csv
from rest_framework.parsers import FileUploadParser, MultiPartParser
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiResponse, OpenApiExample

class StartExamView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ["POST"]
    serializer_class = ExamStartSerializer


    def prepare_response(self, exam, selected_answers_map):
        try:
            selected_question_number = '1'
            first_question = Question.objects.get(id=exam.question_map[selected_question_number])
        except ObjectDoesNotExist:
            raise ValidationError('Question could not be loaded !')

        response_data = ExamResponseSerializer({
            'exam' : exam.id,
            'time_started' : exam.time_started,
            'question' : first_question,
            'selected_answers_map' : selected_answers_map,
            'title' : exam.title,
            'question_number' : selected_question_number,
            'exam_ended':False
        }).data

        return success_response(msg='Exam loaded', data=response_data )
    
    def handle_ongoing_exam(self, exam):
        if time.time() - exam.time_started.timestamp() >= Exam.EXAM_DURATION:
            exam.ended = True
            exam.save()
            return success_response(msg='Exam ended', data = BaseExamSessionSerializer({'exam_ended':True}))

        selected_answers_map = exam.submission.selected_answers_map
        return self.prepare_response(exam, selected_answers_map) #if not ended..push exam to the user

    @extend_schema(
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name='StartExam',
                    fields={
                        'msg': serializers.CharField(allow_null=True),
                        'data': ExamResponseSerializer()
                    }
                ),
                description='JSON response mapping question numbers to selected options.',
                examples=[
                    OpenApiExample(
                        'Ongoing exam',
                        value={
                            'msg': None, 
                            'data': {
                                'exam' : 'exam_id',
                                '...':'........',
                                'exam_ended':False
                            }
                        }
                    ),
                    OpenApiExample(
                        'Ended exam',
                        value={
                            'msg': 'Exam ended', 
                            'data': {
                                'exam_ended': True
                            }
                        }
                    )
                ]
            )
        }
    )
    def post(self, request, *args, **kwargs):
        """
        This is responsible for creating an exam. Two fields can be passed. set only 'course' for creating
        a new exam, and only 'exam' (representing the exam id) for continuing an ongoing exam e.g in the event of 
        a page refresh. 

        If only course is passed, and there is an ongoing exam for that course, that exam will be returned instead.

        Exam takes precedence if both are set.

        Always check for value of exam_ended field before proceeding. A value of false, should end the exam on the FE
        
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception = True)
        exam = serializer.validated_data.get('exam')

        if not exam:
            course = serializer.validated_data.get('course')

            with transaction.atomic(): #so that exam n submission are created in all or none fashion
                ongoing_exam = (
                    Exam.objects
                    .select_for_update() #locks down row so another incomin request does not modify exam..this was added in case a write operation is added in the future to handle_ongoing_exam func , 
                    .filter(course=course, ended=False, initiated_by=request.user)
                    .first()
                )
                # ongoing_exam = Exam.objects.filter(course = course, ended=False, initiated_by = request.user).first() #check if there is an ongoing exam
                if ongoing_exam:
                    return self.handle_ongoing_exam(ongoing_exam)

                max_questions = Exam.MAX_QUESTION_NUMBER
                questions = Question.objects.filter(
                    course = course
                )[:max_questions] #apply LIMIT depending on max questions in SQL, and without order to allow for some randomness in question ordering across users

                if questions.count() < max_questions:
                    return server_error(msg=_(f'{course.capitalize()} exam questions not yet available.'))
                
                question_map = {serial+1 : str(question.id) for serial, question in enumerate(questions)} #note that int as keys will be conv to string in JSON in DB
                empty_answers_map = {serial:'' for serial in range(1,max_questions + 1)}

                exam = Exam.objects.create(
                    title = f'{course.capitalize()}_Exam_{datetime.now().year}',
                    course = course,
                    initiated_by = request.user,
                    question_map = question_map
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
            return self.handle_ongoing_exam(exam) 

           

class AnswerQuestionView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ["POST"]
    serializer_class = AnswerQuestionSerializer

    @extend_schema(
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name='QuestionSelectedAnswerMapping',
                    fields={
                        'msg': serializers.CharField(allow_null=True),
                        'data': inline_serializer(
                            name='ExamStateData',
                            fields={
                                'selected_answers_map': serializers.DictField(
                                    child=serializers.IntegerField(),
                                    help_text="Mapping of question nums to selected options"
                                ),
                                'exam_ended': serializers.BooleanField()
                            }
                        )
                    }
                ),
                description='JSON response mapping question numbers to selected options.',
                examples=[
                    OpenApiExample(
                        'Ongoing exam',
                        value={
                            'msg': None, 
                            'data': {
                                'selected_answers_map': {'1': 10, '2': 20},
                                'exam_ended': False
                            }
                        }
                    ),
                    OpenApiExample(
                        'Ended exam',
                        value={
                            'msg': 'Exam ended', 
                            'data': {
                                'exam_ended': True
                            }
                        }
                    )
                ]
            )
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception = True)
        exam = serializer.validated_data.get('exam')
        if time.time() - exam.time_started.timestamp() >= Exam.EXAM_DURATION:
            exam.ended = True
            exam.save()
            return success_response(msg='Exam ended', data = BaseExamSessionSerializer({'exam_ended':True}))
        question_number = serializer.validated_data.get('question_number')
        answer = serializer.validated_data.get('answer')
        submission_id = serializer.validated_data.get('submission_id')
        with transaction.atomic():
            submission = Submission.objects.select_for_update().get( #lock rows when answering to prevent multiple requests
                id = submission_id
            )
            question_number = str(question_number) #since we mapping to json and json does not use int as keys
            submission.selected_answers_map[question_number] = answer
            submission.save(update_fields=['selected_answers_map'])
        return success_response(msg = 'submitted', data = 
                                AnswerQuestionResponseSerializer(
                                    {'selected_answers_map':submission.selected_answers_map,
                                     'exam_ended':False}
                                ))


class SelectQuestionView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ["POST"]
    serializer_class = SelectQuestionSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception = True)
        exam = serializer.validated_data.get('exam')
        if time.time() - exam.time_started.timestamp() >= Exam.EXAM_DURATION:
            exam.ended = True
            exam.save()
            return error_response(msg='Exam ended')
        question_number = serializer.validated_data.get('question_number')
        selected_answers_map = serializer.validated_data.get('selected_answers_map')
        question = serializer.validated_data.get('question')
        return success_response(data = {
            'question_number' : str(question_number),
            'selected_answers_map' : selected_answers_map,
            'question' : question,
        })
    
class FetchExamsHistoryView(ListAPIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ["GET"]
    serializer_class = ExamHistorySerializer
    pagination_class = CustomPagination
    def get_queryset(self):
        serializer = CourseSerializer(data={'course':self.kwargs.get('course')}).is_valid(raise_exception = True)
        course = serializer.validated_data.get('course')
        return Exam.objects.filter(course = course,initiated_by=self.request.user).order_by('-time_created')


class ExamPerformanceView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BasicExamSerializer
    allowed_methods = ['POST']

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception = True)
        exam = serializer.validated_data.get('exam')
        submission = exam.submission
        if exam.ended == True:
            results_map, final_score = grade_exam_logic(exam, submission.already_scored)
        else:
            if time.time() - exam.time_started.timestamp() >= Exam.EXAM_DURATION:
                exam.ended = True
                exam.save()
                results_map, final_score = grade_exam_logic(exam, submission.already_scored)
            else:
                return error_response(msg='This exam is still ongoing')
            
        return success_response(
            data = {
                'results_map':results_map,
                'final_score':final_score
            }
        )



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



class UploadCSVQuestions(APIView):
    # parser_classes = [FileUploadParser]    
    parser_classes = [MultiPartParser]    
    permission_classes = [IsAuthenticated]

    def post(self,request):
        serializer = CSVUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        file = serializer.validated_data.get('file')
        # csv_file = request.FILES.get('file')
        # if not csv_file:
        #     return error_response("No file provided")

        # Validate file type
        # if not csv_file.name.endswith('.csv'):
        #     return errorResponse("File is not CSV type")

        # df = pd.read_csv(csv_file, delimiter=',',skiprows=3,dtype=str).iloc[:-1]
        # df = df.where(pd.notnull(df), None)

        decoded_file = file.read().decode('utf-8')
        io_string = io.StringIO(decoded_file)
        csv_reader = csv.DictReader(io_string)

        save_data=[]
        timestamp = timezone.now()
        # for index, row in df.iterrows():
        index = 1
        for row in csv_reader:
            try:
                q_instance=Question(
                        question_text=row.get('question_text'),
                        question_type=row.get('question_type'),
                        expected_answer=row.get('expected_answer'),
                        course=row.get('course'),
                        option_a = row.get('option_a'),
                        option_b = row.get('option_b'),
                        option_c = row.get('option_c'),
                        option_d = row.get('option_d'),
                        timestamp = timestamp    
                    )
                q_instance.full_clean()
                save_data.append(q_instance)
            except Exception as e:
                return error_response(f'Error at row {index+1} - {row.get("question_text")}-> {e}')
            index += 1

        try:
            with transaction.atomic():
                Question.objects.bulk_create(save_data)
        except Exception as e:
            return error_response(f'Bulk create error--{e}')
        return success_response(msg="CSV file processed successfully", data={'date_created':timestamp})



            


        






        
        


        

