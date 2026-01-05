from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from .serializers import CustomAuthTokenSerializer, RegisterSerializer, VerifyOTPSerializer, EmailSerializer,LoginResponseSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from utils.response_format import success_response, error_response, server_error
from django.core.mail import EmailMessage
from .models import CustomUser
from django.core.exceptions import ObjectDoesNotExist
import time
from utils.constants import OTP_EXPIRY_MINUTES
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiResponse, OpenApiExample
from rest_framework import serializers

class LoginView(APIView):
    serializer_class = CustomAuthTokenSerializer
    permission_classes = [AllowAny]

    def get_serializer(self, *args, **kwargs):
        return self.serializer_class(*args, **kwargs)

    @extend_schema(
        request=CustomAuthTokenSerializer, 
        responses={200: OpenApiResponse(
                inline_serializer(
                    name='Login successful',
                    fields={
                        'msg': serializers.CharField(),
                        'data': LoginResponseSerializer(),
                    },

            ))}
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return success_response(
            msg = _('Login successful'),
             data = LoginResponseSerializer({
                 'token' :token.key,
                 'email' :user.email,
                 'first_name' :user.first_name,
                 'last_name' :user.last_name
             }).data

        )

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: OpenApiResponse(
                inline_serializer(
                    name='Logout successful',
                    fields={
                        'msg': serializers.CharField(),
                        'data': None,
                    },
               ), 
                examples=[
                    OpenApiExample(
                        'Example 1',
                        value={'msg' : 'Logout successful'}
                    )
                ])}
    )
    def post(self, request):
        # delete the token associated with the user
        request.user.auth_token.delete()
        return success_response(
            msg = _('Logout successful')
        )


class RegisterView(APIView):
    permission_classes = [AllowAny]
    @extend_schema(
        request=RegisterSerializer, 
        responses={
            200: OpenApiResponse(
                inline_serializer(
                    name='success response',
                    fields={
                        'msg': serializers.CharField(),
                        'data': None,
                    }
                ),
                description='Success response with token message',
                examples=[
                    OpenApiExample(
                        'Example 1',
                        value={'msg' : 'Check your email for verification OTP'}
                    )
                ]
            ),

            500: OpenApiResponse(
                inline_serializer(
                    name='error response',
                    fields={
                        'error': serializers.CharField(),
                        'data': None,
                    }
                ),
                description='error response with token sending',
                examples=[
                    OpenApiExample(
                        'Example 1',
                        value={'error' :'Problem sending OTP mail' }
                    )
                ]
            ),
        }
    )
    def post(self,request,*args,**kwargs):
        user = RegisterSerializer(data=request.data)
        user.is_valid(raise_exception=True)
        instance=user.save()
        instance.set_otp()
        # message = EmailMessage(
        #             _("Email verification", f'Your OTP is {instance.otp}. Expires in {OTP_EXPIRY_MINUTES} min', 'acadmsg@gmail.com', [instance.email]))
        try: 
            # message.send()
            print(f'Your OTP is {instance.otp}. Expires in {OTP_EXPIRY_MINUTES} min') #just print out on the console
        except: 
            return server_error(msg=_('Problem sending OTP mail'))
        return success_response(msg=_('Check your email for verification OTP'))



class ResendTokenView(APIView):
    permission_classes = [AllowAny]
    @extend_schema(
        request=EmailSerializer, 
        responses={
            200: OpenApiResponse(
                inline_serializer(
                    name='success response',
                    fields={
                        'msg': serializers.CharField(),
                        'data': None,
                    }
                ),
                description='Success response with token message',
                examples=[
                    OpenApiExample(
                        'Example 1',
                        value={'msg' : 'Check your email for verification OTP'}
                    )
                ]
            ),

            500: OpenApiResponse(
                inline_serializer(
                    name='error response',
                    fields={
                        'error': serializers.CharField(),
                        'data': None,
                    }
                ),
                description='error response with token sending',
                examples=[
                    OpenApiExample(
                        'Example 1',
                        value={'error' :'Problem sending OTP mail' }
                    )
                ]
            ),
        }
    )
    def post(self,request,*args,**kwargs):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data.get('user')
        user.set_otp() 
        # message = EmailMessage(
        #             _("Email verification", f'Your OTP is {user.otp}. Expires in {OTP_EXPIRY_MINUTES} min', 'acadmsg@gmail.com', [user.email]))
        try: 
            # message.send()
            print(f'Your OTP is {user.otp}. Expires in {OTP_EXPIRY_MINUTES} min') #just print out on the console
        except: 
            return server_error(msg=_('Problem sending OTP mail'))
        return success_response(msg=_('Check your email for verification OTP'))

  

class VerifyTokenView(APIView):
    permission_classes = [AllowAny]
    @extend_schema(
        request=VerifyOTPSerializer, 
        responses={
            200: OpenApiResponse(
                inline_serializer(
                    name='success response',
                    fields={
                        'msg': serializers.CharField(),
                        'data': None,
                    }
                ),
                description='Success response with token message',
                examples=[
                    OpenApiExample(
                        'Example 1',
                        value={'msg' : 'Check your email for verification OTP'}
                    )
                ]
            ),

            400: OpenApiResponse(
                inline_serializer(
                    name='error response',
                    fields={
                        'error': serializers.CharField(),
                        'data': None,
                    }
                ),
                description='error response with token validation',
                examples=[
                    OpenApiExample(
                        'Example 1',
                        value={'error' :'Invalid OTP. Request a new one.' }
                    )
                ]
            ),
        }
    )
    def post(self,request,*args,**kwargs):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        otp = serializer.validated_data['otp']
        user = serializer.validated_data['user']
        if otp == user.otp:
            seconds_elapsed = time.time() - user.otp_sent_at.timestamp()
            if seconds_elapsed > OTP_EXPIRY_MINUTES * 60:
                return error_response(msg=_('OTP expired. Request a new one'))
            user.email_verified = True
            user.save()
            return success_response(msg=_('Email Verified Successfully'))
        else:
            return error_response(msg=_('Invalid OTP. Request a new one.'))