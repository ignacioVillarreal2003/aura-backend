from django.contrib import admin
from django.urls import include, path
from drf_spectacular.utils import extend_schema, inline_serializer
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@extend_schema(
    tags=["Health"],
    summary="Health check",
    auth=[],
    responses={
        200: inline_serializer(
            name="HealthResponse",
            fields={"status": serializers.CharField()},
        ),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    return Response({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path("api/v1/health", health_check, name="health-check"),
    path("api/v1/chats/", include("apps.chat.urls")),
    path("api/v1/chats/<int:chat_id>/messages/", include("apps.message.urls")),
    path("api/v1/chats/<int:chat_id>/members/", include("apps.membership.urls")),
    path("", include("django_prometheus.urls")),
]
