import logging
from datetime import datetime

from django.db.models import Count, Q

from apps.message.models.message_feedback import ArtifactFeedback

logger = logging.getLogger(__name__)

_ASSISTANT_FK = "artifact__source_chat__source_assistant_id"


class FeedbackAnalyticsRepository:
    """Aggregations over artifact feedback for the admin analytics dashboard.

    All queries traverse artifact_feedback -> artifact -> chat to attribute
    feedback to the assistant that seeded the chat (``chat.source_assistant_id``).
    Feedback on chats not started from an assistant is grouped under ``None``.
    """

    @staticmethod
    def _range_filter(start: datetime, end: datetime) -> Q:
        return Q(created_at__gte=start, created_at__lte=end)

    def summary(self, start: datetime, end: datetime) -> dict:
        agg = ArtifactFeedback.objects.filter(self._range_filter(start, end)).aggregate(
            total=Count("id"),
            thumbs_up=Count("id", filter=Q(value=1)),
            thumbs_down=Count("id", filter=Q(value=-1)),
        )
        return {
            "total": agg["total"] or 0,
            "thumbs_up": agg["thumbs_up"] or 0,
            "thumbs_down": agg["thumbs_down"] or 0,
        }

    def per_assistant(self, start: datetime, end: datetime) -> list[dict]:
        rows = (
            ArtifactFeedback.objects.filter(self._range_filter(start, end))
            .values(_ASSISTANT_FK)
            .annotate(
                total=Count("id"),
                thumbs_up=Count("id", filter=Q(value=1)),
                thumbs_down=Count("id", filter=Q(value=-1)),
            )
            .order_by()
        )
        return [
            {
                "assistant_id": r[_ASSISTANT_FK],
                "total": r["total"],
                "thumbs_up": r["thumbs_up"],
                "thumbs_down": r["thumbs_down"],
            }
            for r in rows
        ]

    def reason_breakdown(self, start: datetime, end: datetime) -> list[dict]:
        rows = (
            ArtifactFeedback.objects.filter(self._range_filter(start, end), value=-1)
            .values("reason")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        return [{"reason": r["reason"], "count": r["count"]} for r in rows]

    def recent_negative(self, start: datetime, end: datetime, limit: int = 50) -> list[dict]:
        rows = (
            ArtifactFeedback.objects.filter(self._range_filter(start, end), value=-1)
            .order_by("-created_at")
            .values(
                "id",
                "artifact_id",
                "artifact__message_content__message",
                _ASSISTANT_FK,
                "reason",
                "comment",
                "user_id",
                "created_at",
            )[:limit]
        )
        return [
            {
                "id": r["id"],
                "artifact_id": r["artifact_id"],
                "assistant_id": r[_ASSISTANT_FK],
                "reason": r["reason"],
                "comment": r["comment"],
                "user_id": r["user_id"],
                "created_at": r["created_at"],
                "message_excerpt": (r["artifact__message_content__message"] or "")[:280],
            }
            for r in rows
        ]


feedback_analytics_repository = FeedbackAnalyticsRepository()
