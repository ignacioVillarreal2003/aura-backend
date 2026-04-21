from drf_spectacular.utils import OpenApiResponse, inline_serializer
from rest_framework import serializers as drf_serializers

ApiErrorBody = inline_serializer(
    name="ApiErrorBody",
    fields={
        "error": drf_serializers.CharField(help_text="Stable machine-readable error code"),
        "detail": drf_serializers.CharField(help_text="Human-readable message"),
        "status_code": drf_serializers.IntegerField(help_text="HTTP status code (duplicated for clients)"),
    },
)

def standard_error_responses(*status_codes: int) -> dict[int, OpenApiResponse]:
    descriptions = {
        400: "Validation error (invalid query or body).",
        401: "Not authenticated: missing or invalid credentials (see middleware).",
        403: "Forbidden: authenticated but lacking application permissions.",
        404: "Resource not found.",
        409: "Conflict (e.g. duplicate membership or document link).",
        503: "Dependency unavailable (e.g. user profile service when USER_PROFILE_STRICT is enabled).",
    }
    out: dict[int, OpenApiResponse] = {}
    for code in status_codes:
        if code in descriptions:
            out[code] = OpenApiResponse(response=ApiErrorBody, description=descriptions[code])
    return out
