from rest_framework import serializers
from rest_framework.serializers import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import authenticate
from .models import CustomUser
from django.core.exceptions import ObjectDoesNotExist

class CustomAuthTokenSerializer(serializers.Serializer):
    email = serializers.EmailField(
        label=_("Email"),
        write_only=True
    )
    password = serializers.CharField(
        label=_("Password"),
        style={'input_type': 'password'},
        trim_whitespace=False,
        write_only=True
    )


    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(request=self.context.get('request'),
                                email=email, password=password)

            # The authenticate call simply returns None for is_active=False
            # users. (Assuming the default ModelBackend authentication
            # backend.)
            if not user:
                msg = _('Unable to log in with provided credentials.')
                raise serializers.ValidationError(msg, code='authorization')
            if not user.email_verified:
                msg = _('Please verify your email via OTP sent.')
                raise serializers.ValidationError(msg, code='authorization')
        else:
            msg = _('Must include "username" and "password".')
            raise serializers.ValidationError(msg, code='authorization')

        attrs['user'] = user
        return attrs


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('password','email')
        extra_kwargs = {'password':{'write_only':True}}

    def create(self,validated_data):
        user = CustomUser.objects.create_user(
                 password=validated_data["password"],
                 email=validated_data["email"]
                )
        return user

class VerifyOTPSerializer(serializers.Serializer):
    otp = serializers.CharField()
    email = serializers.EmailField()


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()