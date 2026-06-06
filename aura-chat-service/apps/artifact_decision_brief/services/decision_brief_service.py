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
from apps.artifact_decision_brief.exceptions import (
    DecisionBriefAccessDeniedException,
    DecisionBriefNotFoundException,
    LLMServiceException,
)
from apps.artifact_decision_brief.models import ArtifactDecisionBrief
from apps.artifact_decision_brief.repositories.decision_brief_repository import decision_brief_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.artifact.services.artifact_access import assert_detail_access
from django.db import transaction
from apps.artifact.broadcasting import broadcast_artifact_created, broadcast_artifact_progress
from apps.artifact.services.artifact_service import create_artifact_for_content, _cleanup_artifact_interactions
from apps.artifact.llm_context import build_chat_history

logger = logging.getLogger(__name__)


def _assert_access(user_id: int, brief, *, require_contributor: bool = False) -> None:
    assert_detail_access(user_id, brief, DecisionBriefAccessDeniedException(), require_contributor=require_contributor)


def _normalize_options(options: list) -> list:
    normalized = []
    for idx, opt in enumerate(options):
        normalized.append({
            "title": str(opt.get("title", ""))[:300],
            "description": str(opt.get("description", "")),
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
        mode: str,
        source_chat_id: int,
        problem: str,
        context: str,
        risks: str,
        recommendation: str,
        options: list,
) -> tuple:
    artifact = create_artifact_for_content(
        user_id=user_id,
        artifact_type=Artifact.Type.DECISION_BRIEF,
        title=title,
        mode=mode,
        source_chat_id=source_chat_id,
    )
    brief = decision_brief_repository.create(
        user_id=user_id,
        problem=problem,
        context=context,
        risks=risks,
        recommendation=recommendation,
        options=options,
        artifact_id=artifact.id,
    )
    return artifact, brief


class DecisionBriefService:
    def list_decision_briefs(self, user: AuthenticatedUser, chat_id: int):
        AccessControl.require_permissions(user, frozenset({perms.LIST_DECISION_BRIEFS}))
        if chat_repository.get_by_id(chat_id) is None:
            raise ChatNotFoundException()
        if not membership_repository.is_active_member(chat_id, user.id):
            raise ChatAccessDeniedException()
        return decision_brief_repository.list_by_chat(source_chat_id=chat_id)

    def list_all_decision_briefs(self, user: AuthenticatedUser):
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_DECISION_BRIEFS}))
        return decision_brief_repository.list_all()

    def get_decision_brief(self, user: AuthenticatedUser, decision_brief_id: int) -> ArtifactDecisionBrief:
        AccessControl.require_permissions(user, frozenset({perms.GET_DECISION_BRIEF}))
        brief = decision_brief_repository.get_by_id(decision_brief_id)
        if brief is None:
            raise DecisionBriefNotFoundException()
        _assert_access(user.id, brief)
        return brief

    def get_own_decision_brief(self, user: AuthenticatedUser, decision_brief_id: int) -> ArtifactDecisionBrief:
        AccessControl.require_permissions(user, frozenset({perms.EXPORT_DECISION_BRIEF}))
        brief = decision_brief_repository.get_by_id(decision_brief_id)
        if brief is None:
            raise DecisionBriefNotFoundException()
        _assert_access(user.id, brief)
        return brief

    def get_decision_brief_admin_export(self, user: AuthenticatedUser, decision_brief_id: int) -> ArtifactDecisionBrief:
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_EXPORT_DECISION_BRIEF}))
        brief = decision_brief_repository.get_by_id(decision_brief_id)
        if brief is None:
            raise DecisionBriefNotFoundException()
        return brief

    @transaction.atomic
    def update_decision_brief(
            self,
            user: AuthenticatedUser,
            decision_brief_id: int,
            title: Optional[str] = None,
            problem: Optional[str] = None,
            context: Optional[str] = None,
            risks: Optional[str] = None,
            recommendation: Optional[str] = None,
            options: Optional[list] = None,
    ) -> ArtifactDecisionBrief:
        AccessControl.require_permissions(user, frozenset({perms.UPDATE_DECISION_BRIEF}))
        brief = decision_brief_repository.get_by_id_for_update(decision_brief_id)
        if brief is None:
            raise DecisionBriefNotFoundException()
        _assert_access(user.id, brief, require_contributor=True)
        if title is not None:
            artifact_repository.update(brief.artifact, updated_by=user.id, title=title)
        normalized = _normalize_options(options) if options is not None else None
        return decision_brief_repository.update(
            brief,
            updated_by=user.id,
            problem=problem,
            context=context,
            risks=risks,
            recommendation=recommendation,
            options=normalized,
        )

    @transaction.atomic
    def delete_decision_brief(self, user: AuthenticatedUser, decision_brief_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({perms.DELETE_DECISION_BRIEF}))
        brief = decision_brief_repository.get_by_id_for_update(decision_brief_id)
        if brief is None:
            raise DecisionBriefNotFoundException()
        _assert_access(user.id, brief, require_contributor=True)
        decision_brief_repository.soft_delete(brief, deleted_by=user.id)
        _cleanup_artifact_interactions(brief.artifact_id)
        artifact_repository.soft_delete(brief.artifact, deleted_by=user.id)
        logger.info("ArtifactDecisionBrief deleted", extra={"user_id": user.id, "decision_brief_id": decision_brief_id})

    async def generate_decision_brief(
            self,
            user: AuthenticatedUser,
            message: str,
            mode: str,
            chat_id: int,
    ) -> tuple[ArtifactDecisionBrief, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_DECISION_BRIEF_GENERATE}))

        chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        history = await sync_to_async(build_chat_history)(chat_id)

        messages = history + [{"role": "human", "content": message}]
        result_data: dict | None = None
        try:
            async for event in llm_client.generate_decision_brief_stream_events(
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
            mode=mode,
            source_chat_id=chat_id,
            problem=str(result_data.get("problem", "")),
            context=str(result_data.get("context", "")),
            risks=str(result_data.get("risks", "")),
            recommendation=str(result_data.get("recommendation", "")),
            options=options,
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
