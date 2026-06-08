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
from apps.artifact_checklist.exceptions import ChecklistAccessDeniedException, ChecklistNotFoundException, \
    LLMServiceException
from apps.artifact_checklist.models import ArtifactChecklist
from apps.artifact_checklist.repositories.checklist_repository import checklist_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.artifact.services.artifact_access import assert_detail_access
from django.db import transaction
from apps.artifact.broadcasting import broadcast_artifact_created, broadcast_artifact_progress
from apps.artifact.services.artifact_service import create_artifact_for_content, _cleanup_artifact_interactions
from apps.artifact.llm_context import build_chat_history

logger = logging.getLogger(__name__)


@transaction.atomic
def _persist_generated_checklist(*, user_id, title, mode, source_chat_id, sections) -> tuple:
    artifact = create_artifact_for_content(
        user_id=user_id,
        artifact_type=Artifact.Type.CHECKLIST,
        title=title,
        mode=mode,
        source_chat_id=source_chat_id,
    )
    checklist = checklist_repository.create(
        user_id=user_id,
        sections=sections,
        artifact_id=artifact.id,
    )
    return artifact, checklist


def _assert_checklist_access(user_id: int, checklist, *, require_contributor: bool = False) -> None:
    assert_detail_access(user_id, checklist, ChecklistAccessDeniedException(), require_contributor=require_contributor)


def _items_to_sections(items: list) -> list:
    seen: dict[str, list] = {}
    order: list[str] = []
    for item in items:
        name = str(item.get("section", "General"))
        if name not in seen:
            seen[name] = []
            order.append(name)
        seen[name].append(item)

    sections = []
    for pos, name in enumerate(order):
        sorted_items = sorted(seen[name], key=lambda x: int(x.get("order", 0)))
        sections.append({
            "title": name[:200],
            "position": pos,
            "items": [
                {
                    "text": str(it.get("text", "")),
                    "is_checked": bool(it.get("is_checked", False)),
                    "notes": str(it.get("notes", "")),
                    "position": idx,
                }
                for idx, it in enumerate(sorted_items)
            ],
        })
    return sections


class ChecklistService:
    def list_checklists(self, user: AuthenticatedUser, chat_id: int):
        AccessControl.require_permissions(user, frozenset({perms.LIST_CHECKLISTS}))
        if chat_repository.get_by_id(chat_id) is None:
            raise ChatNotFoundException()
        if not membership_repository.is_active_member(chat_id, user.id):
            raise ChatAccessDeniedException()
        return checklist_repository.list_by_chat(source_chat_id=chat_id)

    def list_all_checklists(self, user: AuthenticatedUser):
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_CHECKLISTS}))
        return checklist_repository.list_all()

    def get_checklist(self, user: AuthenticatedUser, checklist_id: int) -> ArtifactChecklist:
        AccessControl.require_permissions(user, frozenset({perms.GET_CHECKLIST}))
        checklist = checklist_repository.get_by_id(checklist_id)
        if checklist is None:
            raise ChecklistNotFoundException()
        _assert_checklist_access(user.id, checklist)
        return checklist

    def get_own_checklist(self, user: AuthenticatedUser, checklist_id: int) -> ArtifactChecklist:
        AccessControl.require_permissions(user, frozenset({perms.EXPORT_CHECKLIST}))
        checklist = checklist_repository.get_by_id(checklist_id)
        if checklist is None:
            raise ChecklistNotFoundException()
        _assert_checklist_access(user.id, checklist)
        return checklist

    def get_checklist_admin_export(self, user: AuthenticatedUser, checklist_id: int) -> ArtifactChecklist:
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_EXPORT_CHECKLIST}))
        checklist = checklist_repository.get_by_id(checklist_id)
        if checklist is None:
            raise ChecklistNotFoundException()
        return checklist

    @transaction.atomic
    def update_checklist(
            self,
            user: AuthenticatedUser,
            checklist_id: int,
            title: Optional[str] = None,
            sections: Optional[list] = None,
    ) -> ArtifactChecklist:
        AccessControl.require_permissions(user, frozenset({perms.UPDATE_CHECKLIST}))
        checklist = checklist_repository.get_by_id_for_update(checklist_id)
        if checklist is None:
            raise ChecklistNotFoundException()
        _assert_checklist_access(user.id, checklist, require_contributor=True)
        if title is not None:
            artifact_repository.update(checklist.artifact, updated_by=user.id, title=title)
        return checklist_repository.update(checklist, updated_by=user.id, sections=sections)

    @transaction.atomic
    def delete_checklist(self, user: AuthenticatedUser, checklist_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({perms.DELETE_CHECKLIST}))
        checklist = checklist_repository.get_by_id_for_update(checklist_id)
        if checklist is None:
            raise ChecklistNotFoundException()
        _assert_checklist_access(user.id, checklist, require_contributor=True)
        checklist_repository.soft_delete(checklist, deleted_by=user.id)
        _cleanup_artifact_interactions(checklist.artifact_id)
        artifact_repository.soft_delete(checklist.artifact, deleted_by=user.id)
        logger.info("ArtifactChecklist deleted", extra={"user_id": user.id, "checklist_id": checklist_id})

    async def generate_checklist(
            self,
            user: AuthenticatedUser,
            message: str,
            mode: str,
            chat_id: int,
    ) -> tuple[ArtifactChecklist, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_CHECKLIST_GENERATE}))

        chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        history = await sync_to_async(build_chat_history)(chat_id)

        messages = history + [{"role": "human", "content": message}]
        result_data: dict | None = None
        try:
            async for event in llm_client.generate_checklist_stream_events(
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
                        "LLM checklist stream error: %s", event.get("message", ""),
                        extra={"user_id": user.id, "code": event.get("code")},
                    )
                    raise LLMServiceException()
        except HttpClientException as e:
            logger.error(
                "LLM checklist-generate stream failed: %s",
                str(e),
                extra={"user_id": user.id, "status_code": e.status_code},
                exc_info=True,
            )
            raise LLMServiceException() from e

        if result_data is None:
            logger.error("LLM checklist stream ended without complete event", extra={"user_id": user.id})
            raise LLMServiceException()

        title = str(result_data.get("title", "")).strip()
        items = result_data.get("items") or []
        out_messages = result_data.get("messages") or []
        fragments = llm_client.normalize_fragments(result_data.get("fragments"))

        if not title:
            logger.error("LLM returned empty title for checklist", extra={"user_id": user.id})
            raise LLMServiceException()
        if not items:
            logger.error("LLM returned empty items for checklist", extra={"user_id": user.id})
            raise LLMServiceException()

        sections = _items_to_sections(items)
        artifact, checklist = await sync_to_async(_persist_generated_checklist)(
            user_id=user.id,
            title=title,
            mode=mode,
            source_chat_id=chat_id,
            sections=sections,
        )
        logger.info(
            "ArtifactChecklist generated and saved",
            extra={
                "user_id": user.id,
                "checklist_id": checklist.id,
                "source_chat_id": chat_id,
                "artifact_id": artifact.id,
            },
        )
        await broadcast_artifact_created(chat_id, artifact)
        return checklist, out_messages, fragments


checklist_service = ChecklistService()
