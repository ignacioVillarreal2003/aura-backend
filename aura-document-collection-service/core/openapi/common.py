from drf_spectacular.utils import OpenApiResponse, inline_serializer
from rest_framework import serializers as drf_serializers

ApiErrorBody = inline_serializer(
    name="ApiErrorBody",
    fields={
        "error": drf_serializers.CharField(
            help_text=(
                "Stable, machine-readable error code (examples: missing_token, invalid_token, validation_error, "
                "document_collection_not_found, duplicate_document_link, insufficient_permissions)."
            ),
        ),
        "detail": drf_serializers.JSONField(
            help_text=(
                "Explanation for operators: string detail from domain exceptions or structured validation errors "
                "(dict/list) emitted by Django REST Framework after the custom exception handler wraps them."
            ),
        ),
        "status_code": drf_serializers.IntegerField(
            help_text="HTTP status echoed in the payload for resilient clients parsing JSON only.",
        ),
    },
)


def standard_error_responses(*status_codes: int) -> dict[int, OpenApiResponse]:
    descriptions = {
        400: (
            "Request validation failed or service-to-service headers are malformed "
            "(e.g. invalid X-User-Id)."
        ),
        401: (
            "Caller is unauthenticated or credentials were rejected: missing Bearer token, "
            "malformed Authorization header, or invalid/expired JWT as determined by middleware."
        ),
        403: (
            "Caller is authenticated but forbidden: insufficient application-level permission "
            "`insufficient_permissions`, or token blocked upstream."
        ),
        404: (
            "Resource does not exist, is soft-deleted, or—for some JWT flows—a user referenced by auth cannot be found."
        ),
        409: (
            "Integrity or uniqueness conflict prevented the operation "
            "(duplicate document link, duplicate compartment assignment, catalogue duplicates, FK still in use, etc.)."
        ),
        503: (
            "Dependency temporarily unavailable—the authentication upstream timed out or returned 5xx, "
            "or another integrated service degraded."
        ),
    }
    out: dict[int, OpenApiResponse] = {}
    for code in status_codes:
        if code in descriptions:
            out[code] = OpenApiResponse(response=ApiErrorBody, description=descriptions[code])
    return out
