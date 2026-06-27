import logging
from typing import Optional
from asgiref.sync import sync_to_async

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import llm_client
from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.artifact.models import Artifact
from apps.artifact_timeline.exceptions import TimelineAccessDeniedException, TimelineNotFoundException, \
    LLMServiceException
from apps.artifact_timeline.models import ArtifactTimeline
from apps.artifact_timeline.repositories.timeline_repository import timeline_repository
from django.db import transaction
from apps.artifact.broadcasting import broadcast_artifact_created, broadcast_artifact_progress
from apps.artifact.services.artifact_service import create_artifact_for_content
from apps.artifact.services.artifact_crud_service import ArtifactCrudService
from apps.artifact.llm_context import build_chat_history

logger = logging.getLogger(__name__)

_DOCUMENTS_ONLY_INSTRUCTION = "Construí la línea de tiempo a partir del o los documentos adjuntos."


def _normalize_events(events: list) -> list:
    normalized = []
    for idx, ev in enumerate(events):
        normalized.append({
            "title": str(ev.get("title", "")),
            "description": str(ev.get("description", "")),
            "occurred_label": str(ev.get("occurred_label", "")),
            "position": idx,
        })
    return normalized


@transaction.atomic
def _persist_generated_timeline(
        *,
        user_id: int,
        title: str,
        query: str,
        retrieve_context: bool | None,
        process_documents: bool | None,
        document_ids: list[int],
        source_chat_id: int,
        description: str,
        events: list,
        fragments=None,
) -> tuple:
    artifact = create_artifact_for_content(
        user_id=user_id,
        artifact_type=Artifact.Type.TIMELINE,
        retrieve_context=retrieve_context,
        process_documents=process_documents,
        document_ids=document_ids,
        source_chat_id=source_chat_id,
        fragments=fragments,
    )
    timeline = timeline_repository.create(
        user_id=user_id,
        description=description,
        events=events,
        artifact_id=artifact.id,
        title=title,
        query=query,
    )
    return artifact, timeline


class TimelineService(ArtifactCrudService):
    repository = timeline_repository
    not_found_exc = TimelineNotFoundException
    access_denied_exc = TimelineAccessDeniedException
    log_model = "ArtifactTimeline"
    log_id_key = "timeline_id"
    perm_list = perms.LIST_TIMELINES
    perm_manage = perms.MANAGE_TIMELINES
    perm_get = perms.GET_TIMELINE
    perm_export = perms.EXPORT_TIMELINE
    perm_manage_export = perms.MANAGE_EXPORT_TIMELINE
    perm_delete = perms.DELETE_TIMELINE
    logger = logger

    def list_timelines(self, user: AuthenticatedUser, chat_id: int):
        return self._list_by_chat(user, chat_id)

    def list_all_timelines(self, user: AuthenticatedUser):
        return self._list_all(user)

    def get_timeline(self, user: AuthenticatedUser, timeline_id: int) -> ArtifactTimeline:
        return self._get(user, timeline_id)

    def get_own_timeline(self, user: AuthenticatedUser, timeline_id: int) -> ArtifactTimeline:
        return self._get_own(user, timeline_id)

    def get_timeline_admin_export(self, user: AuthenticatedUser, timeline_id: int) -> ArtifactTimeline:
        return self._get_admin_export(user, timeline_id)

    def delete_timeline(self, user: AuthenticatedUser, timeline_id: int) -> None:
        self._delete(user, timeline_id)

    async def generate_timeline(
            self,
            user: AuthenticatedUser,
            message: str,
            chat_id: int,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> tuple[ArtifactTimeline, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_TIMELINE_GENERATE}))

        chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        system_prompt = chat.system_prompt if chat else None
        response_style = chat.response_style if chat else None
        history = await sync_to_async(build_chat_history)(chat_id)

        human_text = message.strip() if message else _DOCUMENTS_ONLY_INSTRUCTION
        messages = history + [{"role": "human", "content": human_text}]
        result_data: dict | None = None
        try:
            async for event in llm_client.generate_timeline_stream_events(
                    messages=messages,
                    user=user,
                    chat_id=chat_id,
                    system_prompt=system_prompt,
                    response_style=response_style,
                    retrieve_context=retrieve_context,
                    process_documents=process_documents,
                    document_ids=document_ids,
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
        description = str(result_data.get("description", ""))

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
            query=message,
            retrieve_context=retrieve_context,
            process_documents=process_documents,
            document_ids=document_ids or [],
            source_chat_id=chat_id,
            description=description,
            events=events,
            fragments=fragments,
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
