import logging
from typing import Optional
from asgiref.sync import sync_to_async

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import llm_client
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.artifact.models import Artifact
from apps.artifact.repositories.artifact_repository import artifact_repository
from apps.artifact_timeline.exceptions import TimelineAccessDeniedException, TimelineNotFoundException, \
    LLMServiceException
from apps.artifact_timeline.models import ArtifactTimeline
from apps.artifact_timeline.repositories.timeline_repository import timeline_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.artifact.services.artifact_access import assert_detail_access
from django.db import transaction
from apps.artifact.broadcasting import broadcast_artifact_created, broadcast_artifact_progress
from apps.artifact.services.artifact_service import create_artifact_for_content, _cleanup_artifact_interactions
from apps.artifact.llm_context import build_chat_history

logger = logging.getLogger(__name__)


def _assert_timeline_access(user_id: int, timeline, *, require_contributor: bool = False) -> None:
    assert_detail_access(user_id, timeline, TimelineAccessDeniedException(), require_contributor=require_contributor)


def _normalize_events(events: list) -> list:
    normalized = []
    for idx, ev in enumerate(events):
        normalized.append({
            "title": str(ev.get("title", ev.get("event", ""))),
            "description": str(ev.get("description", "")),
            "occurred_at": ev.get("occurred_at"),
            "occurred_label": str(ev.get("occurred_label", "")),
            "position": idx,
        })
    return normalized


@transaction.atomic
def _persist_generated_timeline(
        *,
        user_id: int,
        title: str,
        mode: str,
        source_chat_id: int,
        summary: str,
        events: list,
) -> tuple:
    artifact = create_artifact_for_content(
        user_id=user_id,
        artifact_type=Artifact.Type.TIMELINE,
        title=title,
        mode=mode,
        source_chat_id=source_chat_id,
    )
    timeline = timeline_repository.create(
        user_id=user_id,
        summary=summary,
        events=events,
        artifact_id=artifact.id,
    )
    return artifact, timeline


class TimelineService:
    def list_timelines(self, user: AuthenticatedUser, chat_id: int):
        AccessControl.require_permissions(user, frozenset({perms.LIST_TIMELINES}))
        if chat_repository.get_by_id(chat_id) is None:
            raise ChatNotFoundException()
        if not membership_repository.is_active_member(chat_id, user.id):
            raise ChatAccessDeniedException()
        return timeline_repository.list_by_chat(source_chat_id=chat_id)

    def list_all_timelines(self, user: AuthenticatedUser):
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_TIMELINES}))
        return timeline_repository.list_all()

    def get_timeline(self, user: AuthenticatedUser, timeline_id: int) -> ArtifactTimeline:
        AccessControl.require_permissions(user, frozenset({perms.GET_TIMELINE}))
        timeline = timeline_repository.get_by_id(timeline_id)
        if timeline is None:
            raise TimelineNotFoundException()
        _assert_timeline_access(user.id, timeline)
        return timeline

    def get_own_timeline(self, user: AuthenticatedUser, timeline_id: int) -> ArtifactTimeline:
        AccessControl.require_permissions(user, frozenset({perms.EXPORT_TIMELINE}))
        timeline = timeline_repository.get_by_id(timeline_id)
        if timeline is None:
            raise TimelineNotFoundException()
        _assert_timeline_access(user.id, timeline)
        return timeline

    def get_timeline_admin_export(self, user: AuthenticatedUser, timeline_id: int) -> ArtifactTimeline:
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_EXPORT_TIMELINE}))
        timeline = timeline_repository.get_by_id(timeline_id)
        if timeline is None:
            raise TimelineNotFoundException()
        return timeline

    @transaction.atomic
    def update_timeline(
            self,
            user: AuthenticatedUser,
            timeline_id: int,
            title: Optional[str] = None,
            summary: Optional[str] = None,
            events: Optional[list] = None,
    ) -> ArtifactTimeline:
        AccessControl.require_permissions(user, frozenset({perms.UPDATE_TIMELINE}))
        timeline = timeline_repository.get_by_id_for_update(timeline_id)
        if timeline is None:
            raise TimelineNotFoundException()
        _assert_timeline_access(user.id, timeline, require_contributor=True)
        if title is not None:
            artifact_repository.update(timeline.artifact, updated_by=user.id, title=title)
        normalized = _normalize_events(events) if events is not None else None
        return timeline_repository.update(
            timeline, updated_by=user.id, summary=summary, events=normalized
        )

    @transaction.atomic
    def delete_timeline(self, user: AuthenticatedUser, timeline_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({perms.DELETE_TIMELINE}))
        timeline = timeline_repository.get_by_id_for_update(timeline_id)
        if timeline is None:
            raise TimelineNotFoundException()
        _assert_timeline_access(user.id, timeline, require_contributor=True)
        timeline_repository.soft_delete(timeline, deleted_by=user.id)
        _cleanup_artifact_interactions(timeline.artifact_id)
        artifact_repository.soft_delete(timeline.artifact, deleted_by=user.id)
        logger.info("ArtifactTimeline deleted", extra={"user_id": user.id, "timeline_id": timeline_id})

    async def generate_timeline(
            self,
            user: AuthenticatedUser,
            message: str,
            mode: str,
            chat_id: int,
    ) -> tuple[ArtifactTimeline, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_TIMELINE_GENERATE}))

        chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        history = await sync_to_async(build_chat_history)(chat_id)

        messages = history + [{"role": "human", "content": message}]
        result_data: dict | None = None
        try:
            async for event in llm_client.generate_timeline_stream_events(
                    messages=messages,
                    mode=mode,
                    user=user,
                    chat_id=chat_id,
            ):
                et = event.get("type")
                if et == "progress":
                    await broadcast_artifact_progress(chat_id, str(event.get("step", "")),
                                                      str(event.get("message", "")))
                elif et == "complete":
                    result_data = event.get("result") or {}
                elif et == "error":
                    logger.error(
                        "LLM timeline stream error: %s", event.get("message", ""),
                        extra={"user_id": user.id, "code": event.get("code")},
                    )
                    raise LLMServiceException()
        except HttpClientException as e:
            logger.error(
                "LLM timeline-generate stream failed: %s",
                str(e),
                extra={"user_id": user.id, "status_code": e.status_code},
                exc_info=True,
            )
            raise LLMServiceException() from e

        if result_data is None:
            logger.error("LLM timeline stream ended without complete event", extra={"user_id": user.id})
            raise LLMServiceException()

        title = str(result_data.get("title", "")).strip()
        raw_events = result_data.get("events") or []
        out_messages = result_data.get("messages") or []
        fragments = llm_client.normalize_fragments(result_data.get("fragments"))
        summary = str(result_data.get("summary", ""))

        if not title:
            logger.error("LLM returned empty title for timeline", extra={"user_id": user.id})
            raise LLMServiceException()
        if not raw_events:
            logger.error("LLM returned empty events for timeline", extra={"user_id": user.id})
            raise LLMServiceException()

        events = _normalize_events(raw_events)
        artifact, timeline = await sync_to_async(_persist_generated_timeline)(
            user_id=user.id,
            title=title,
            mode=mode,
            source_chat_id=chat_id,
            summary=summary,
            events=events,
        )
        logger.info(
            "ArtifactTimeline generated and saved",
            extra={
                "user_id": user.id,
                "timeline_id": timeline.id,
                "source_chat_id": chat_id,
                "artifact_id": artifact.id,
            },
        )
        await broadcast_artifact_created(chat_id, artifact)
        return timeline, out_messages, fragments


timeline_service = TimelineService()
