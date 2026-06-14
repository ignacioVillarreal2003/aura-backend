"""Kubernetes-style health probes.

Three distinct endpoints with different failure semantics:

* **liveness**  — is the process up and able to answer? No dependency I/O, so a
  transient DB/Redis blip never triggers a pod restart.
* **readiness** — are all dependencies reachable? Returns 503 when not, so the
  orchestrator removes the pod from the load balancer without restarting it.
* **startup**   — gates liveness/readiness until dependencies are reachable on boot.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from core.health.checks import dependency_checks

_LIVENESS_RESPONSE = inline_serializer(
    name="LivenessResponse",
    fields={"status": serializers.CharField()},
)
_READINESS_RESPONSE = inline_serializer(
    name="ReadinessResponse",
    fields={
        "status": serializers.CharField(),
        "checks": serializers.DictField(child=serializers.CharField()),
    },
)


@extend_schema(
    tags=["Health"],
    summary="Liveness probe",
    description="Returns 200 while the process is up. Performs no dependency I/O.",
    auth=[],
    responses={200: _LIVENESS_RESPONSE},
)
@api_view(["GET"])
@permission_classes([AllowAny])
def liveness(_request: Request) -> Response:
    return Response({"status": "alive"})


def _readiness_response() -> Response:
    results = dependency_checks()
    checks = {result.name: ("ok" if result.ok else "error") for result in results}
    all_ok = all(result.ok for result in results)
    return Response(
        {"status": "ready" if all_ok else "not_ready", "checks": checks},
        status=status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@extend_schema(
    tags=["Health"],
    summary="Readiness probe",
    description=(
        "**200** with per-dependency `checks` when database and Redis are reachable; "
        "**503** otherwise so the pod is taken out of rotation without being restarted."
    ),
    auth=[],
    responses={200: _READINESS_RESPONSE, 503: _READINESS_RESPONSE},
)
@api_view(["GET"])
@permission_classes([AllowAny])
def readiness(_request: Request) -> Response:
    return _readiness_response()


@extend_schema(
    tags=["Health"],
    summary="Startup probe",
    description="Same checks as readiness; gates liveness/readiness until dependencies are reachable on boot.",
    auth=[],
    responses={200: _READINESS_RESPONSE, 503: _READINESS_RESPONSE},
)
@api_view(["GET"])
@permission_classes([AllowAny])
def startup(_request: Request) -> Response:
    return _readiness_response()
