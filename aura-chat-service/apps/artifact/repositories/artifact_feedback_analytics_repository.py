import logging
from datetime import datetime
from django.db.models import Count, Q

from apps.artifact.models.artifact_feedback import ArtifactFeedback

logger = logging.getLogger(__name__)

_ASSISTANT_FK = "artifact__source_chat__source_assistant_id"
_ALIVE_ARTIFACT = Q(artifact__deleted_at__isnull=True)


class FeedbackAnalyticsRepository:
    @staticmethod
    def _range_filter(start: datetime, end: datetime) -> Q:
        return Q(created_at__gte=start, created_at__lte=end)

    @staticmethod
    def _extra_filters(
            chat_id: int | None = None,
            artifact_type: str | None = None,
            user_id: int | None = None,
            reason: str | None = None,
    ) -> Q:
        q = Q()
        if chat_id is not None:
            q &= Q(artifact__source_chat_id=chat_id)
        if artifact_type is not None:
            q &= Q(artifact__type=artifact_type)
        if user_id is not None:
            q &= Q(created_by=user_id)
        if reason is not None:
            q &= Q(reason=reason)
        return q

    def summary(
            self,
            start: datetime,
            end: datetime,
            chat_id: int | None = None,
            artifact_type: str | None = None,
            user_id: int | None = None,
            reason: str | None = None,
    ) -> dict:
        extra = self._extra_filters(chat_id=chat_id, artifact_type=artifact_type, user_id=user_id, reason=reason)
        agg = ArtifactFeedback.objects.filter(self._range_filter(start, end), _ALIVE_ARTIFACT, extra).aggregate(
            total=Count("id"),
            thumbs_up=Count("id", filter=Q(value=1)),
            thumbs_down=Count("id", filter=Q(value=-1)),
        )
        return {
            "total": agg["total"] or 0,
            "thumbs_up": agg["thumbs_up"] or 0,
            "thumbs_down": agg["thumbs_down"] or 0,
        }

    def per_assistant(
            self,
            start: datetime,
            end: datetime,
            chat_id: int | None = None,
            artifact_type: str | None = None,
            user_id: int | None = None,
            reason: str | None = None,
    ) -> list[dict]:
        extra = self._extra_filters(chat_id=chat_id, artifact_type=artifact_type, user_id=user_id, reason=reason)
        rows = (
            ArtifactFeedback.objects.filter(self._range_filter(start, end), _ALIVE_ARTIFACT, extra)
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

    def reason_breakdown(
            self,
            start: datetime,
            end: datetime,
            chat_id: int | None = None,
            artifact_type: str | None = None,
            user_id: int | None = None,
            reason: str | None = None,
    ) -> list[dict]:
        extra = self._extra_filters(chat_id=chat_id, artifact_type=artifact_type, user_id=user_id, reason=reason)
        rows = (
            ArtifactFeedback.objects.filter(self._range_filter(start, end), _ALIVE_ARTIFACT, value=-1)
            .filter(extra)
            .values("reason")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        return [{"reason": r["reason"], "count": r["count"]} for r in rows]

    def recent_negative(
            self,
            start: datetime,
            end: datetime,
            limit: int = 50,
            chat_id: int | None = None,
            artifact_type: str | None = None,
            user_id: int | None = None,
            reason: str | None = None,
    ) -> list[dict]:
        extra = self._extra_filters(chat_id=chat_id, artifact_type=artifact_type, user_id=user_id, reason=reason)
        rows = (
            ArtifactFeedback.objects.filter(self._range_filter(start, end), _ALIVE_ARTIFACT, value=-1)
            .filter(extra)
            .order_by("-created_at")
            .values(
                "id",
                "artifact_id",
                "artifact__message_content__message",
                _ASSISTANT_FK,
                "reason",
                "comment",
                "created_by",
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
                "user_id": r["created_by"],
                "created_at": r["created_at"],
                "message_excerpt": (r["artifact__message_content__message"] or "")[:280],
            }
            for r in rows
        ]


feedback_analytics_repository = FeedbackAnalyticsRepository()
