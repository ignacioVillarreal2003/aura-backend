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
from apps.artifact_decision_brief.exceptions import (
    DecisionBriefAccessDeniedException,
    DecisionBriefNotFoundException,
    LLMServiceException,
)
from apps.artifact_decision_brief.models import ArtifactDecisionBrief
from apps.artifact_decision_brief.repositories.decision_brief_repository import decision_brief_repository
from django.db import transaction
from apps.artifact.broadcasting import broadcast_artifact_created, broadcast_artifact_progress
from apps.artifact.services.artifact_service import create_artifact_for_content
from apps.artifact.services.artifact_crud_service import ArtifactCrudService
from apps.artifact.llm_context import build_chat_history

logger = logging.getLogger(__name__)

_DOCUMENTS_ONLY_INSTRUCTION = "Generá el resumen para la toma de decisiones a partir del o los documentos adjuntos."


def _normalize_options(options: list) -> list:
    normalized = []
    for idx, opt in enumerate(options):
        normalized.append({
            "title": str(opt.get("title", ""))[:300],
            "pros": str(opt.get("pros", "")),
            "cons": str(opt.get("cons", "")),
            "is_recommended": bool(opt.get("is_recommended", False)),
            "position": idx,
        })
    has_recommended = False
    for opt in normalized:
        if opt["is_recommended"]:
            if has_recommended:
                opt["is_recommended"] = False
            else:
                has_recommended = True
    return normalized


@transaction.atomic
def _persist_generated_decision_brief(
        *,
        user_id: int,
        title: str,
        query: str,
        retrieve_context: bool | None,
        process_documents: bool | None,
        document_ids: list[int],
        source_chat_id: int,
        description: str,
        context: str,
        risks: str,
        recommendation: str,
        options: list,
        fragments=None,
) -> tuple:
    artifact = create_artifact_for_content(
        user_id=user_id,
        artifact_type=Artifact.Type.DECISION_BRIEF,
        retrieve_context=retrieve_context,
        process_documents=process_documents,
        document_ids=document_ids,
        source_chat_id=source_chat_id,
        fragments=fragments,
    )
    brief = decision_brief_repository.create(
        user_id=user_id,
        description=description,
        context=context,
        risks=risks,
        recommendation=recommendation,
        options=options,
        artifact_id=artifact.id,
        title=title,
        query=query,
    )
    return artifact, brief


class DecisionBriefService(ArtifactCrudService):
    repository = decision_brief_repository
    not_found_exc = DecisionBriefNotFoundException
    access_denied_exc = DecisionBriefAccessDeniedException
    log_model = "ArtifactDecisionBrief"
    log_id_key = "decision_brief_id"
    perm_list = perms.LIST_DECISION_BRIEFS
    perm_manage = perms.MANAGE_DECISION_BRIEFS
    perm_get = perms.GET_DECISION_BRIEF
    perm_export = perms.EXPORT_DECISION_BRIEF
    perm_manage_export = perms.MANAGE_EXPORT_DECISION_BRIEF
    perm_delete = perms.DELETE_DECISION_BRIEF
    logger = logger

    def list_decision_briefs(self, user: AuthenticatedUser, chat_id: int):
        return self._list_by_chat(user, chat_id)

    def list_all_decision_briefs(self, user: AuthenticatedUser):
        return self._list_all(user)

    def get_decision_brief(self, user: AuthenticatedUser, decision_brief_id: int) -> ArtifactDecisionBrief:
        return self._get(user, decision_brief_id)

    def get_own_decision_brief(self, user: AuthenticatedUser, decision_brief_id: int) -> ArtifactDecisionBrief:
        return self._get_own(user, decision_brief_id)

    def get_decision_brief_admin_export(self, user: AuthenticatedUser, decision_brief_id: int) -> ArtifactDecisionBrief:
        return self._get_admin_export(user, decision_brief_id)

    def delete_decision_brief(self, user: AuthenticatedUser, decision_brief_id: int) -> None:
        self._delete(user, decision_brief_id)

    async def generate_decision_brief(
            self,
            user: AuthenticatedUser,
            message: str,
            chat_id: int,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> tuple[ArtifactDecisionBrief, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_DECISION_BRIEF_GENERATE}))

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
            async for event in llm_client.generate_decision_brief_stream_events(
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
                        "LLM decision-brief stream error: %s", event.get("message", ""),
                        extra={"user_id": user.id, "code": event.get("code")},
                    )
                    raise LLMServiceException()
        except HttpClientException as e:
            logger.error(
                "LLM decision-brief-generate stream failed: %s",
                str(e),
                extra={"user_id": user.id, "status_code": e.status_code},
                exc_info=True,
            )
            raise LLMServiceException() from e

        if result_data is None:
            logger.error("LLM decision-brief stream ended without complete event", extra={"user_id": user.id})
            raise LLMServiceException()

        title = str(result_data.get("title", "")).strip()
        raw_options = result_data.get("options") or []
        out_messages = result_data.get("messages") or []
        fragments = llm_client.normalize_fragments(result_data.get("fragments"))

        if not title:
            logger.error("LLM returned empty title for decision-brief", extra={"user_id": user.id})
            raise LLMServiceException()
        if not raw_options:
            logger.error("LLM returned empty options for decision-brief", extra={"user_id": user.id})
            raise LLMServiceException()

        options = _normalize_options(raw_options)
        artifact, brief = await sync_to_async(_persist_generated_decision_brief)(
            user_id=user.id,
            title=title,
            query=message,
            retrieve_context=retrieve_context,
            process_documents=process_documents,
            document_ids=document_ids or [],
            source_chat_id=chat_id,
            description=str(result_data.get("description", "")),
            context=str(result_data.get("context", "")),
            risks=str(result_data.get("risks", "")),
            recommendation=str(result_data.get("recommendation", "")),
            options=options,
            fragments=fragments,
        )
        logger.info(
            "ArtifactDecisionBrief generated and saved",
            extra={
                "user_id": user.id,
                "decision_brief_id": brief.id,
                "source_chat_id": chat_id,
                "artifact_id": artifact.id,
            },
        )
        await broadcast_artifact_created(chat_id, artifact)
        return brief, out_messages, fragments


decision_brief_service = DecisionBriefService()
