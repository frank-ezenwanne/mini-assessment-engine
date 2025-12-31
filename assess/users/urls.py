from django.urls import path,include
from .views import LoginView, LogoutView, RegisterView, ResendTokenView, VerifyTokenView

urlpatterns = [
    path('auth/login', LoginView.as_view(), name='login-view'),
    path('auth/logout', LogoutView.as_view(), name='logout-view'),
    path('auth/register', RegisterView.as_view(), name='register-view'),
    path('auth/resend-token', ResendTokenView.as_view(), name='resend-token-view'),
    path('auth/verify-token', VerifyTokenView.as_view(), name='verify-token-view')
]