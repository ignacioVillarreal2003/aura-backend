import logging
from datetime import datetime, timedelta
from django.utils import timezone

from apps.assistant.models import Assistant
from apps.artifact.repositories.artifact_feedback_analytics_repository import feedback_analytics_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import VIEW_FEEDBACK_ANALYTICS

logger = logging.getLogger(__name__)

_DEFAULT_DAYS = 30
_MAX_DAYS = 3650
_NO_ASSISTANT_LABEL = "Chats sin asistente"


def _satisfaction_rate(up: int, down: int) -> float | None:
    total = up + down
    if total == 0:
        return None
    return round(up / total, 4)


class FeedbackAnalyticsService:
    def get_analytics(
            self,
            user: AuthenticatedUser,
            days: int | None = None,
            chat_id: int | None = None,
            artifact_type: str | None = None,
            user_id: int | None = None,
            reason: str | None = None,
    ) -> dict:
        AccessControl.require_permissions(user, frozenset({VIEW_FEEDBACK_ANALYTICS}))

        window_days = self._normalize_days(days)
        end = timezone.now()
        start = end - timedelta(days=window_days)

        filters = {
            "chat_id": chat_id,
            "artifact_type": artifact_type,
            "user_id": user_id,
            "reason": reason,
        }

        summary = feedback_analytics_repository.summary(start, end, **filters)
        per_assistant = feedback_analytics_repository.per_assistant(start, end, **filters)
        reasons = feedback_analytics_repository.reason_breakdown(start, end, **filters)
        recent = feedback_analytics_repository.recent_negative(start, end, **filters)

        names = self._resolve_assistant_names(
            [row["assistant_id"] for row in per_assistant]
            + [row["assistant_id"] for row in recent]
        )

        return {
            "window_days": window_days,
            "start": start,
            "end": end,
            "summary": {
                **summary,
                "satisfaction_rate": _satisfaction_rate(
                    summary["thumbs_up"], summary["thumbs_down"]
                ),
            },
            "assistants": self._build_assistant_rows(per_assistant, names),
            "reasons": reasons,
            "recent_negative": [
                {**row, "assistant_name": names.get(row["assistant_id"], _NO_ASSISTANT_LABEL)}
                for row in recent
            ],
        }

    @staticmethod
    def _normalize_days(days: int | None) -> int:
        if days is None:
            return _DEFAULT_DAYS
        return max(1, min(int(days), _MAX_DAYS))

    @staticmethod
    def _resolve_assistant_names(assistant_ids: list[int | None]) -> dict[int, str]:
        ids = {aid for aid in assistant_ids if aid is not None}
        if not ids:
            return {}
        return dict(
            Assistant.objects.all_with_deleted()
            .filter(id__in=ids)
            .values_list("id", "name")
        )

    @staticmethod
    def _build_assistant_rows(per_assistant: list[dict], names: dict[int, str]) -> list[dict]:
        rows = [
            {
                "assistant_id": row["assistant_id"],
                "assistant_name": names.get(row["assistant_id"], _NO_ASSISTANT_LABEL),
                "total": row["total"],
                "thumbs_up": row["thumbs_up"],
                "thumbs_down": row["thumbs_down"],
                "satisfaction_rate": _satisfaction_rate(row["thumbs_up"], row["thumbs_down"]),
            }
            for row in per_assistant
        ]
        rows.sort(key=lambda r: (r["thumbs_down"], r["total"]), reverse=True)
        return rows


feedback_analytics_service = FeedbackAnalyticsService()
