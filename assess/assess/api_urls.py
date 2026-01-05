from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('exam/',include('exams.urls')),
    path('users/',include('users.urls')),
    path('swagger-schema/', SpectacularAPIView.as_view(), name='schema'),
    path('swagger-docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
