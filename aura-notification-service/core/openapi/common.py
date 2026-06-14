from drf_spectacular.utils import OpenApiResponse, inline_serializer
from rest_framework import serializers as drf_serializers


ApiErrorBody = inline_serializer(
    name="ApiErrorBody",
    fields={
        "error": drf_serializers.CharField(help_text="Stable machine-readable error code"),
        "detail": drf_serializers.CharField(help_text="Human-readable message"),
        "status_code": drf_serializers.IntegerField(help_text="HTTP status code"),
    },
)


def standard_error_responses(*status_codes: int) -> dict[int, OpenApiResponse]:
    descriptions = {
        400: "Validation error (invalid query or body).",
        401: "Not authenticated: missing or invalid credentials.",
        403: "Forbidden: authenticated but lacking permissions.",
        404: "Resource not found.",
        409: "Conflict.",
        429: "Too many requests — rate limit exceeded.",
        503: "Dependency service temporarily unavailable.",
    }
    return {
        code: OpenApiResponse(response=ApiErrorBody, description=descriptions[code])
        for code in status_codes
        if code in descriptions
    }
