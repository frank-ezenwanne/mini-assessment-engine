from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, serializers
from rest_framework.throttling import ScopedRateThrottle
from .serializers import ExamStartSerializer, AnswerQuestionSerializer, SelectQuestionSerializer,\
      BasicExamSerializer,CourseSerializer, CSVUploadSerializer,BaseExamSessionSerializer,\
        ExamResponseSerializer,ExamHistoryResponseSerializer,AnswerQuestionResponseSerializer,\
            SelectQuestionResponseSerializer,ResultResponseSerializer
from .models import Exam, Question, Submission
from datetime import datetime
from utils.response_format import server_error, success_response, error_response
from utils.result_grade import grade_exam_logic
from utils.pagination import CustomPagination
from utils.cache_questions import prepare_question_cache
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from django.utils.functional import cached_property
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
import time
import io
import csv
from rest_framework.parsers import MultiPartParser
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiResponse, OpenApiExample, OpenApiParameter
from drf_spectacular.types import OpenApiTypes


class StartExamView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ["POST"]
    serializer_class = ExamStartSerializer
    throttle_scope = 'exam_start'
    throttle_classes = [ScopedRateThrottle]


    def prepare_response(self, exam, selected_answers_map):

        selected_question_number = '1'
        question_cache = cache.get_or_set(
            f'exam_cache_{exam.id}',
            lambda: prepare_question_cache(exam),
            timeout = Exam.EXAM_DURATION
        )

        try:
            first_question = question_cache[selected_question_number]
        except KeyError:
            raise ValidationError('Question could not be loaded')

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
            return success_response(msg='Ongoing Exam ended', data = BaseExamSessionSerializer({'exam_ended':True}).data)

        selected_answers_map = exam.submission.selected_answers_map
        return self.prepare_response(exam, selected_answers_map) #if not ended..push exam to the user

    @extend_schema(
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name='StartExamSuccessResponse',
                    fields={
                        'msg': serializers.CharField(allow_null=True),
                        'data': ExamResponseSerializer()
                    }
                ),
                description='Exam information.',
                examples=[
                    OpenApiExample(
                        'OngoingExam',
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
                        'EndedExam',
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
        

        If exam is already past timestamp or ended, it still returns a success message but with the 
        exam_ended field as True
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
        
                if ongoing_exam:
                    return self.handle_ongoing_exam(ongoing_exam)

                max_questions = Exam.MAX_QUESTION_NUMBER
                questions = Question.objects.filter(
                    course = course
                )[:max_questions] #apply LIMIT depending on max questions in SQL, and without order to allow for some randomness in question ordering across users

                if questions.count() < max_questions:
                    return server_error(msg=_(f'{course.capitalize()} exam questions not yet available.'))
                
                question_map = {str(serial+1) : str(question.id) for serial, question in enumerate(questions)} #note that int as keys will be conv to string in JSON in DB
                question_map_cache = {str(serial+1) : question for serial, question in enumerate(questions)} #prepare cache

            
                empty_answers_map = {str(serial):'' for serial in range(1,max_questions + 1)}

                exam = Exam.objects.create(
                    title = f'{course.capitalize()}_Exam_{datetime.now().month}_/_{datetime.now().year}',
                    course = course,
                    initiated_by = request.user,
                    question_map = question_map
                )

                cache.set(f'exam_cache_{exam.id}', question_map_cache, timeout=Exam.EXAM_DURATION) #cache exam questions for exam duration
            
                Submission.objects.create(
                    exam = exam,
                    student = request.user,
                    selected_answers_map = empty_answers_map
                )

                return self.prepare_response(exam, empty_answers_map)

        else:
            if exam.time_ended or exam.ended == True:
                return success_response(msg='Exam ended', data = BaseExamSessionSerializer({'exam_ended':True}).data)
            return self.handle_ongoing_exam(exam) 

           

class AnswerQuestionView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ["POST"]
    serializer_class = AnswerQuestionSerializer
    throttle_scope = 'exam_answer'
    throttle_classes = [ScopedRateThrottle]

    @extend_schema(
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name='AnswerQuestionSuccessResponse',
                    fields={
                        'msg': serializers.CharField(allow_null=True),
                        'data': AnswerQuestionResponseSerializer()
                    }
                ),
                description='JSON response mapping question numbers to selected options.',
                examples=[
                    OpenApiExample(
                        'OngoingExam',
                        value={
                            'msg': None, 
                            'data': {
                                'selected_answers_map': {'1': 'a', '2': 'b'},
                                'exam_ended': False
                            }
                        }
                    ),
                    OpenApiExample(
                        'EndedExam',
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
        Allows a student to answer a question at a time in the exam.

        If exam is already past timestamp or ended, it still returns a success message but with the 
        exam_ended field as True
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception = True)
        exam = serializer.validated_data.get('exam')
        if exam.ended or exam.time_ended:
            return success_response(msg='Exam ended', data = BaseExamSessionSerializer({'exam_ended':True}).data)
        if time.time() - exam.time_started.timestamp() >= Exam.EXAM_DURATION:
            exam.ended = True
            exam.save()
            return success_response(msg='Exam ended', data = BaseExamSessionSerializer({'exam_ended':True}).data)
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
                                ).data)


class SelectQuestionView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ["POST"]
    serializer_class = SelectQuestionSerializer
    throttle_scope = 'exam_select_question'
    throttle_classes = [ScopedRateThrottle]

    @extend_schema(
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name='SelectQuestionSuccessResponse',
                    fields={
                        'msg': serializers.CharField(allow_null=True),
                        'data': SelectQuestionResponseSerializer()
                    }
                ),
                description='Response to Selecting a Question.',
                examples=[
                    OpenApiExample(
                        'OngoingExam',
                        value={
                            'msg': None, 
                            'data': {
                                'question_number' : '1',
                                'selected_answers_map': {'1': 'a', '2': 'b'},
                                '...':'........',
                                'exam_ended':False
                            }
                        }
                    ),
                    OpenApiExample(
                        'EndedExam',
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
        Allows the student to select any question in the exam with a question number and exam id
        and returns the question details

        If exam is already past timestamp or ended, it still returns a success message but with the 
        exam_ended field as True
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception = True)
        exam = serializer.validated_data.get('exam')
        if exam.ended or exam.time_ended:
            return success_response(msg='Exam ended', data = BaseExamSessionSerializer({'exam_ended':True}).data)
        if time.time() - exam.time_started.timestamp() >= Exam.EXAM_DURATION:
            exam.ended = True
            exam.save()
            return success_response(msg='Exam ended', data = BaseExamSessionSerializer({'exam_ended':True}).data)
        question_number = serializer.validated_data.get('question_number')
        selected_answers_map = serializer.validated_data.get('selected_answers_map')
        question = serializer.validated_data.get('question')
        return success_response(
            data=SelectQuestionResponseSerializer({
                'question_number' : str(question_number),
                'selected_answers_map' : selected_answers_map,
                'question' : question,
                'exam_ended':False
            }).data
        )

    
class FetchExamsHistoryView(ListAPIView):

    permission_classes = [IsAuthenticated]
    allowed_methods = ["GET"]
    serializer_class = ExamHistoryResponseSerializer
    pagination_class = CustomPagination #doc ordering specification is inside here..to override swagger's default ordering
    throttle_scope = 'exam_general'
    throttle_classes = [ScopedRateThrottle]

    @cached_property  #run validate stuff here to avoid making get_queryset mixed up with validate logic
    def validated_course(self):
        serializer = CourseSerializer(data={'course': self.kwargs.get('course')})
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data.get('course')

    def get_queryset(self): 
        return Exam.objects.filter(course = self.validated_course,
                        initiated_by=self.request.user).order_by('-time_started')
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='course',   
                type=OpenApiTypes.STR, 
                location=OpenApiParameter.PATH, 
                description='The course subject to filter history.',
                required=True,
                enum=[choice[0] for choice in Question.COURSE_OPTIONS] #To Restrict the choices for frontend
            ),
            OpenApiParameter(
                name='page', 
                type=OpenApiTypes.INT, 
                location=OpenApiParameter.QUERY, 
                description='To specify a page number within the paginated result.',
                required=False
            ),
            OpenApiParameter(
                name='page_size', 
                type=OpenApiTypes.INT, 
                location=OpenApiParameter.QUERY, 
                description='The Number of instances to return per page.',
                required=False
            ),
        ],
        responses={200: ExamHistoryResponseSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        """
        This Fetches all exams for the current user
        This view is paginated, the data is returned alongside page attributes in a
        page_info object. 
        
        In page_info,

        count is Number of instances across all pages.

        next is url to next page (nullable).

        previous is url to previous page (nullable)
        """
        return super().get(request, *args, **kwargs)



class ExamPerformanceView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BasicExamSerializer
    allowed_methods = ['POST']
    throttle_scope = 'exam_general'
    throttle_classes = [ScopedRateThrottle]

    @extend_schema(
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name='ExamPerformanceSuccessResponse',
                    fields={
                        'msg': serializers.CharField(allow_null=True),
                        'data': ResultResponseSerializer()
                    }
                ),
            ),

            400: OpenApiResponse(
                response=inline_serializer(
                    name='ExamStillOngoingError',
                    many=True,
                    fields={
                        'error': serializers.CharField(),
                        'data': serializers.CharField(allow_null=True)
                    }
                ),examples=[
                    OpenApiExample(
                        'OngoingExam',
                        value={
                            'error': 'Exam is still Ongoing', 
                            'data': None
                        })]
            )
        }
    )

    
    def post(self, request, *args, **kwargs):
        """
        Returns result for a particular exam if already ended else it returns an 
        error stating the exam is still ongoing

        The results_map is a mapping of question number to question, selected_answer, is_correct, expected_answer
        """
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
            data = ResultResponseSerializer({
                'results_map':results_map,
                'final_score':final_score,
                'exam_ended':True
            }).data
        )



class TerminateGradeExamView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ["POST"]
    serializer_class = BasicExamSerializer
    throttle_scope = 'exam_start'
    throttle_classes = [ScopedRateThrottle]


    @extend_schema(
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name='TerminateExamSuccessResponse',
                    fields={
                        'msg': serializers.CharField(allow_null=True),
                        'data': ResultResponseSerializer()
                    }
                ),
            )
        }
    )
    def post(self, request, *args, **kwargs):
        """
        Ends the exam and returns the result

        The results_map is a mapping of question number to question, selected_answer, is_correct, expected_answer
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception = True)
        exam = serializer.validated_data.get('exam')
        exam.ended = True
        exam.save()
        submission = exam.submission
        results_map, final_score = grade_exam_logic(exam, submission.already_scored)
        return success_response(
            data = ResultResponseSerializer({
                'results_map':results_map,
                'final_score':final_score,
                'exam_ended':True
            }).data
        )



class UploadCSVQuestions(APIView): 
    parser_classes = [MultiPartParser]    
    permission_classes = [IsAuthenticated]
    throttle_scope = 'uploads'
    throttle_classes = [ScopedRateThrottle]

    @extend_schema(
        request={
            'multipart/form-data': CSVUploadSerializer,
        },
        responses={
                201: OpenApiResponse(
                    response=inline_serializer(
                        name='UploadSuccessfulResponse',
                        fields={
                            'msg': serializers.CharField(help_text='Success message'),
                            'data': inline_serializer(
                                name='UploadSuccessfulDataField',
                                fields={
                                        'date_created':serializers.DateTimeField()
                                        }
                                    )
                                 }
                            ),
                ),
                    
                
            400: OpenApiResponse(
                response=inline_serializer(
                    name='UploadErrorResponse',
                    many=True,
                    fields={
                        'error': serializers.CharField(),
                        'data': serializers.CharField(allow_null=True),
                    }
                ),
                                               
                description='Error in Processing',
                examples=[
                    OpenApiExample(
                        'Example1',
                        value={'error' :'Error at row 1 -','data':None }
                    )
                ]
            )
        },
        summary="Upload exam questions via CSV",
        description="Expects a multipart form-data request with a 'file' key."
    )
    def post(self,request):
        serializer = CSVUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        file = serializer.validated_data.get('file')
        decoded_file = file.read().decode('utf-8')
        io_string = io.StringIO(decoded_file)
        csv_reader = csv.DictReader(io_string)

        save_data=[]
        timestamp = timezone.now()
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
                return error_response(f'Error at row {index+1} - having question text-{row.get("question_text")}--> {e}')
            index += 1

        try:
            with transaction.atomic():
                Question.objects.bulk_create(save_data)
        except Exception as e:
            return error_response(f'Bulk create error--{e}')
        return success_response(msg="CSV file processed successfully", data={'date_created':timestamp},status=status.HTTP_201_CREATED)



            


        






        
        


        

