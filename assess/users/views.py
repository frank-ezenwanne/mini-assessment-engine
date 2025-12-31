from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from .serializers import CustomAuthTokenSerializer, RegisterSerializer, VerifyOTPSerializer, EmailSerializer
from rest_framework.permissions import IsAuthenticated
from utils.response_format import success_response, error_response, server_error
from django.core.mail import EmailMessage
from .models import CustomUser
from django.core.exceptions import ObjectDoesNotExist
import time
from utils.constants import OTP_EXPIRY_MINUTES
from django.utils.translation import gettext_lazy as _

class LoginView(APIView):
    serializer_class = CustomAuthTokenSerializer
    def get_serializer_context(self):
        return {
            'request': self.request,
            'format': self.format_kwarg,
            'view': self
        }

    def get_serializer(self, *args, **kwargs):
        kwargs['context'] = self.get_serializer_context()
        return self.serializer_class(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return success_response(
            msg = _('Login successful'),
            data = {
             'token': token.key,
             'email':user.email,
             'first_name':user.first_name,
             'last_name':user.last_name
             }

        )

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # delete the token associated with the user
        request.user.auth_token.delete()
        return success_response(
            msg = _('Login successful')
        )


class RegisterView(APIView):

    serializer_class = RegisterSerializer

    def post(self,request,*args,**kwargs):
        user = RegisterSerializer(data=request.data)
        user.is_valid(raise_exception=True)
        instance=user.save()
        instance.set_otp()
        message = EmailMessage(
                    _("Email verification", f'Your OTP is {instance.otp}. Expires in {OTP_EXPIRY_MINUTES} min', 'acadmsg@gmail.com', [instance.email]))
        try: 
            message.send()
        except: 
            return server_error(msg=_('Problem sending OTP mail'))
        return success_response(msg=_('Check your email for verification OTP'))


class ResendTokenView(APIView):
    def post(self,request,*args,**kwargs):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = CustomUser.objects.get(email=serializer.validated_data['email'])
        except ObjectDoesNotExist:
            return error_response(msg=_('User not found'))
        user.set_otp() 
        message = EmailMessage(
                    _("Email verification", f'Your OTP is {user.otp}. Expires in {OTP_EXPIRY_MINUTES} min', 'acadmsg@gmail.com', [user.email]))
        try: 
            message.send()
        except: 
            return server_error(msg=_('Problem sending OTP mail'))
        return success_response(msg=_('Check your email for verification OTP'))

  

class VerifyTokenView(APIView):
    def post(self,request,*args,**kwargs):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        otp = serializer.validated_data['otp']
        email = serializer.validated_data['email']
        try:
            user = CustomUser.objects.get(email=email)
        except ObjectDoesNotExist:
            return error_response(msg=_('User not found'))

        if otp == user.otp:
            seconds_elapsed = time.time() - user.otp_sent_at.timestamp()
            if seconds_elapsed > OTP_EXPIRY_MINUTES * 60:
                return error_response(msg=_('OTP expired. Request a new one'))
            user.email_verified = True
            user.save()
            return success_response(msg=_('Email Verified Successfully'))
        else:
            return error_response(msg=_('Invalid OTP. Request a new one.'))