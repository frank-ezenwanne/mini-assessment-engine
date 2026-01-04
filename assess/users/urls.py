from django.urls import path
from .views import LoginView, LogoutView, RegisterView, ResendTokenView, VerifyTokenView

urlpatterns = [
    path('auth/login', LoginView.as_view(), name='login'),
    path('auth/logout', LogoutView.as_view(), name='logout'),
    path('auth/register', RegisterView.as_view(), name='register'),
    path('auth/resend-token', ResendTokenView.as_view(), name='resend-token'),
    path('auth/verify-token', VerifyTokenView.as_view(), name='verify-token')
]