import logging
from typing import Optional
from asgiref.sync import sync_to_async

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import DecisionBriefGenerateResult, llm_client
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.artifact.models import Artifact
from apps.artifact.repositories.artifact_repository import artifact_repository
from apps.decision_brief.exceptions import (
    DecisionBriefAccessDeniedException,
    DecisionBriefNotFoundException,
    LLMServiceException,
)
from apps.decision_brief.models import DecisionBrief
from apps.decision_brief.repositories.decision_brief_repository import decision_brief_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.message.models.chat_message import ChatMessage
from apps.message.repositories.message_repository import message_repository

logger = logging.getLogger(__name__)


def _assert_access(user_id: int, brief: DecisionBrief, *, require_contributor: bool = False) -> None:
    if brief.created_by == user_id:
        return
    if brief.source_chat_id is not None:
        checker = (
            membership_repository.is_active_contributor
            if require_contributor
            else membership_repository.is_active_member
        )
        if checker(brief.source_chat_id, user_id):
            return
    raise DecisionBriefAccessDeniedException()


def _normalize_options(options: list) -> list:
    normalized = []
    for idx, opt in enumerate(options):
        normalized.append({
            "title": str(opt.get("title", "")),
            "description": str(opt.get("description", "")),
            "pros": str(opt.get("pros", "")),
            "cons": str(opt.get("cons", "")),
            "is_recommended": bool(opt.get("is_recommended", False)),
            "position": idx,
        })
    return normalized


class DecisionBriefService:
    def list_decision_briefs(self, user: AuthenticatedUser, chat_id: Optional[int] = None):
        AccessControl.require_permissions(user, frozenset({perms.LIST_DECISION_BRIEFS}))
        if chat_id is not None:
            if chat_repository.get_by_id(chat_id) is None:
                raise ChatNotFoundException()
            if not membership_repository.is_active_member(chat_id, user.id):
                raise ChatAccessDeniedException()
            return decision_brief_repository.list_by_chat(source_chat_id=chat_id)
        return decision_brief_repository.list_by_user(user_id=user.id)

    def list_all_decision_briefs(self, user: AuthenticatedUser):
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_DECISION_BRIEFS}))
        return decision_brief_repository.list_all()

    def get_decision_brief(self, user: AuthenticatedUser, decision_brief_id: int) -> DecisionBrief:
        AccessControl.require_permissions(user, frozenset({perms.GET_DECISION_BRIEF}))
        brief = decision_brief_repository.get_by_id(decision_brief_id)
        if brief is None:
            raise DecisionBriefNotFoundException()
        _assert_access(user.id, brief)
        return brief

    def get_own_decision_brief(self, user: AuthenticatedUser, decision_brief_id: int) -> DecisionBrief:
        AccessControl.require_permissions(user, frozenset({perms.EXPORT_DECISION_BRIEF}))
        brief = decision_brief_repository.get_by_id(decision_brief_id)
        if brief is None:
            raise DecisionBriefNotFoundException()
        _assert_access(user.id, brief)
        return brief

    def get_decision_brief_admin_export(self, user: AuthenticatedUser, decision_brief_id: int) -> DecisionBrief:
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_EXPORT_DECISION_BRIEF}))
        brief = decision_brief_repository.get_by_id(decision_brief_id)
        if brief is None:
            raise DecisionBriefNotFoundException()
        return brief

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
    ) -> DecisionBrief:
        AccessControl.require_permissions(user, frozenset({perms.UPDATE_DECISION_BRIEF}))
        brief = decision_brief_repository.get_by_id(decision_brief_id)
        if brief is None:
            raise DecisionBriefNotFoundException()
        _assert_access(user.id, brief, require_contributor=True)
        normalized = _normalize_options(options) if options is not None else None
        return decision_brief_repository.update(
            brief,
            updated_by=user.id,
            title=title,
            problem=problem,
            context=context,
            risks=risks,
            recommendation=recommendation,
            options=normalized,
        )

    def delete_decision_brief(self, user: AuthenticatedUser, decision_brief_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({perms.DELETE_DECISION_BRIEF}))
        brief = decision_brief_repository.get_by_id(decision_brief_id)
        if brief is None:
            raise DecisionBriefNotFoundException()
        _assert_access(user.id, brief, require_contributor=True)
        decision_brief_repository.soft_delete(brief, deleted_by=user.id)
        logger.info("DecisionBrief deleted", extra={"user_id": user.id, "decision_brief_id": decision_brief_id})

    async def generate_decision_brief(
            self,
            user: AuthenticatedUser,
            message: str,
            mode: str,
            chat_id: Optional[int] = None,
    ) -> tuple[DecisionBrief, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_DECISION_BRIEF_GENERATE}))

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
            result: DecisionBriefGenerateResult = await llm_client.generate_decision_brief(
                messages=messages,
                mode=mode,
                user=user,
                chat_id=chat_id,
            )
        except HttpClientException as e:
            logger.error(
                "LLM decision-brief-generate failed: %s",
                str(e),
                extra={"user_id": user.id, "status_code": e.status_code},
                exc_info=True,
            )
            raise LLMServiceException() from e

        if not result.title or not result.title.strip():
            logger.error("LLM returned empty title for decision-brief", extra={"user_id": user.id})
            raise LLMServiceException()
        if not result.options:
            logger.error("LLM returned empty options for decision-brief", extra={"user_id": user.id})
            raise LLMServiceException()

        options = _normalize_options(result.options)
        artifact_id = await sync_to_async(self._create_artifact_header)(
            user_id=user.id,
            title=result.title,
            source_chat_id=chat_id,
        )
        brief = await sync_to_async(decision_brief_repository.create)(
            user_id=user.id,
            title=result.title,
            problem=result.problem,
            context=result.context,
            risks=result.risks,
            recommendation=result.recommendation,
            options=options,
            mode=mode,
            source_chat_id=chat_id,
            artifact_id=artifact_id,
        )
        logger.info(
            "DecisionBrief generated and saved",
            extra={
                "user_id": user.id,
                "decision_brief_id": brief.id,
                "source_chat_id": chat_id,
                "artifact_id": artifact_id,
            },
        )
        return brief, result.messages, result.fragments

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
                type=Artifact.Type.DECISION_BRIEF,
                title=title,
                status=Artifact.Status.FINAL,
                source_chat_id=source_chat_id,
            )
            return artifact.id
        except Exception:
            logger.warning(
                "Failed to create artifact header for decision-brief",
                extra={"user_id": user_id, "source_chat_id": source_chat_id},
                exc_info=True,
            )
            return None


decision_brief_service = DecisionBriefService()
