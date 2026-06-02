import logging

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.message.serializers.analytics import FeedbackAnalyticsResponse
from apps.message.services.feedback_analytics_service import feedback_analytics_service
from core.openapi.common import standard_error_responses

logger = logging.getLogger(__name__)

_DAYS_PARAM = OpenApiParameter(
    name="days",
    type=int,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Trailing window size in days (default 30, max 365).",
)


class FeedbackAnalyticsView(APIView):
    @extend_schema(
        tags=["Feedback"],
        summary="Feedback analytics dashboard (admin)",
        description=(
            "Aggregated thumbs up/down feedback over a trailing window: overall satisfaction, "
            "a per-assistant breakdown (worst performers first), a reason breakdown for negative "
            "feedback, and recent negative entries with comments. Requires `VIEW_FEEDBACK_ANALYTICS`."
        ),
        parameters=[_DAYS_PARAM],
        responses={200: FeedbackAnalyticsResponse, **standard_error_responses(401, 403)},
    )
    def get(self, request: Request) -> Response:
        days = self._parse_days(request.query_params.get("days"))
        data = feedback_analytics_service.get_analytics(user=request.user, days=days)
        return Response(FeedbackAnalyticsResponse(data).data)

    @staticmethod
    def _parse_days(raw: str | None) -> int | None:
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
