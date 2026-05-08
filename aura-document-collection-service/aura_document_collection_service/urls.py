from django.urls import include, path
from drf_spectacular.utils import extend_schema, inline_serializer
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@extend_schema(
    tags=["Health"],
    summary="Liveness ping",
    description=(
        "`AllowAny` route excluded from JWT/service-key middleware—ideal for load balancers, Kubernetes probes, "
        "or sanity checks immediately after rollout. Successful responses return JSON **{ \"status\": \"ok\" }** with "
        "HTTP 200; carries no datastore nor dependency chatter."
    ),
    auth=[],
    responses={
        200: inline_serializer(
            name="HealthResponse",
            fields={
                "status": serializers.CharField(
                    help_text="Literal `ok` when the ASGI/WSGI stack answers; extend later if richer diagnostics emerge.",
                    default="ok",
                ),
            },
        ),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    return Response({"status": "ok"})


urlpatterns = [
    path("", include("django_prometheus.urls")),
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
    path("api/v1/", include("aura_document_collection_service.api_urls")),
]
