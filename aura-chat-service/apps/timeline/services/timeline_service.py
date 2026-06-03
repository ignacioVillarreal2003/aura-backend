import logging
from typing import Optional
from asgiref.sync import sync_to_async

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import TimelineGenerateResult, llm_client
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.artifact.models import Artifact
from apps.artifact.repositories.artifact_repository import artifact_repository
from apps.timeline.exceptions import TimelineAccessDeniedException, TimelineNotFoundException, LLMServiceException
from apps.timeline.models import Timeline
from apps.timeline.repositories.timeline_repository import timeline_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.message.models.chat_message import ChatMessage
from apps.message.repositories.message_repository import message_repository

logger = logging.getLogger(__name__)


def _assert_timeline_access(user_id: int, timeline: Timeline, *, require_contributor: bool = False) -> None:
    if timeline.created_by == user_id:
        return
    if timeline.source_chat_id is not None:
        checker = (
            membership_repository.is_active_contributor
            if require_contributor
            else membership_repository.is_active_member
        )
        if checker(timeline.source_chat_id, user_id):
            return
    raise TimelineAccessDeniedException()


def _normalize_events(events: list) -> list:
    normalized = []
    for idx, ev in enumerate(events):
        normalized.append({
            "event": str(ev.get("event", "")),
            "description": str(ev.get("description", "")),
            "occurred_at": ev.get("occurred_at"),
            "occurred_label": str(ev.get("occurred_label", "")),
            "source_document_id": ev.get("source_document_id"),
            "position": idx,
        })
    return normalized


class TimelineService:
    def list_timelines(self, user: AuthenticatedUser, chat_id: Optional[int] = None):
        AccessControl.require_permissions(user, frozenset({perms.LIST_TIMELINES}))
        if chat_id is not None:
            if chat_repository.get_by_id(chat_id) is None:
                raise ChatNotFoundException()
            if not membership_repository.is_active_member(chat_id, user.id):
                raise ChatAccessDeniedException()
            return timeline_repository.list_by_chat(source_chat_id=chat_id)
        return timeline_repository.list_by_user(user_id=user.id)

    def list_all_timelines(self, user: AuthenticatedUser):
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_TIMELINES}))
        return timeline_repository.list_all()

    def get_timeline(self, user: AuthenticatedUser, timeline_id: int) -> Timeline:
        AccessControl.require_permissions(user, frozenset({perms.GET_TIMELINE}))
        timeline = timeline_repository.get_by_id(timeline_id)
        if timeline is None:
            raise TimelineNotFoundException()
        _assert_timeline_access(user.id, timeline)
        return timeline

    def get_own_timeline(self, user: AuthenticatedUser, timeline_id: int) -> Timeline:
        AccessControl.require_permissions(user, frozenset({perms.EXPORT_TIMELINE}))
        timeline = timeline_repository.get_by_id(timeline_id)
        if timeline is None:
            raise TimelineNotFoundException()
        _assert_timeline_access(user.id, timeline)
        return timeline

    def get_timeline_admin_export(self, user: AuthenticatedUser, timeline_id: int) -> Timeline:
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_EXPORT_TIMELINE}))
        timeline = timeline_repository.get_by_id(timeline_id)
        if timeline is None:
            raise TimelineNotFoundException()
        return timeline

    def update_timeline(
            self,
            user: AuthenticatedUser,
            timeline_id: int,
            title: Optional[str] = None,
            summary: Optional[str] = None,
            events: Optional[list] = None,
    ) -> Timeline:
        AccessControl.require_permissions(user, frozenset({perms.UPDATE_TIMELINE}))
        timeline = timeline_repository.get_by_id(timeline_id)
        if timeline is None:
            raise TimelineNotFoundException()
        _assert_timeline_access(user.id, timeline, require_contributor=True)
        normalized = _normalize_events(events) if events is not None else None
        return timeline_repository.update(
            timeline, updated_by=user.id, title=title, summary=summary, events=normalized
        )

    def delete_timeline(self, user: AuthenticatedUser, timeline_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({perms.DELETE_TIMELINE}))
        timeline = timeline_repository.get_by_id(timeline_id)
        if timeline is None:
            raise TimelineNotFoundException()
        _assert_timeline_access(user.id, timeline, require_contributor=True)
        timeline_repository.soft_delete(timeline, deleted_by=user.id)
        logger.info("Timeline deleted", extra={"user_id": user.id, "timeline_id": timeline_id})

    async def generate_timeline(
            self,
            user: AuthenticatedUser,
            message: str,
            mode: str,
            chat_id: Optional[int] = None,
    ) -> tuple[Timeline, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_TIMELINE_GENERATE}))

        history: list[dict] = []
        if chat_id is not None:
            chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
            if chat is None:
                raise ChatNotFoundException()
            is_contributor = await sync_to_async(membership_repository.is_active_contributor)(chat_id, user.id)
            if not is_contributor:
                raise ChatAccessDeniedException()
            recent = await sync_to_async(message_repository.get_recent_messages)(chat_id, limit=20)
            recent.reverse()
            for msg in recent:
                role = "human" if msg.sender_type == ChatMessage.SenderType.USER else "assistant"
                history.append({"role": role, "content": msg.message})

        messages = history + [{"role": "human", "content": message}]
        try:
            result: TimelineGenerateResult = await llm_client.generate_timeline(
                messages=messages,
                mode=mode,
                user=user,
                chat_id=chat_id,
            )
        except HttpClientException as e:
            logger.error(
                "LLM timeline-generate failed: %s",
                str(e),
                extra={"user_id": user.id, "status_code": e.status_code},
                exc_info=True,
            )
            raise LLMServiceException() from e

        if not result.title or not result.title.strip():
            logger.error("LLM returned empty title for timeline", extra={"user_id": user.id})
            raise LLMServiceException()
        if not result.events:
            logger.error("LLM returned empty events for timeline", extra={"user_id": user.id})
            raise LLMServiceException()

        events = _normalize_events(result.events)
        artifact_id = await sync_to_async(self._create_artifact_header)(
            user_id=user.id,
            title=result.title,
            source_chat_id=chat_id,
        )
        timeline = await sync_to_async(timeline_repository.create)(
            user_id=user.id,
            title=result.title,
            summary=result.summary,
            events=events,
            mode=mode,
            source_chat_id=chat_id,
            artifact_id=artifact_id,
        )
        logger.info(
            "Timeline generated and saved",
            extra={
                "user_id": user.id,
                "timeline_id": timeline.id,
                "source_chat_id": chat_id,
                "artifact_id": artifact_id,
            },
        )
        return timeline, result.messages, result.fragments

    @staticmethod
    def _create_artifact_header(
            *,
            user_id: int,
            title: str,
            source_chat_id: Optional[int],
    ) -> Optional[int]:
        try:
            artifact = artifact_repository.create(
                user_id=user_id,
                type=Artifact.Type.TIMELINE,
                title=title,
                status=Artifact.Status.FINAL,
                source_chat_id=source_chat_id,
            )
            return artifact.id
        except Exception:
            logger.warning(
                "Failed to create artifact header for timeline",
                extra={"user_id": user_id, "source_chat_id": source_chat_id},
                exc_info=True,
            )
            return None


timeline_service = TimelineService()
