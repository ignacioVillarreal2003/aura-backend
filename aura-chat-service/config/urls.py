from django.urls import path, include
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def health_check(request):
    return Response({'status': 'healthy', 'service': 'Aura Chat Service'})


urlpatterns = [
    path('health', health_check),
    path('api/v1/', include('chat.urls')),
]
