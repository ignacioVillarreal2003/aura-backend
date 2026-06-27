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
from apps.artifact_checklist.exceptions import ChecklistAccessDeniedException, ChecklistItemNotFoundException, \
    ChecklistNotFoundException, LLMServiceException
from apps.artifact_checklist.models import ArtifactChecklist, ArtifactChecklistItem
from apps.artifact_checklist.repositories.checklist_repository import checklist_repository
from django.db import transaction
from apps.artifact.broadcasting import broadcast_artifact_created, broadcast_artifact_progress
from apps.artifact.services.artifact_service import create_artifact_for_content
from apps.artifact.services.artifact_crud_service import ArtifactCrudService
from apps.artifact.llm_context import build_chat_history

logger = logging.getLogger(__name__)

_DOCUMENTS_ONLY_INSTRUCTION = "Generá la checklist de verificación a partir del o los documentos adjuntos."


@transaction.atomic
def _persist_generated_checklist(*, user_id, title, description, query, retrieve_context, process_documents, document_ids, source_chat_id, sections, fragments=None) -> tuple:
    artifact = create_artifact_for_content(
        user_id=user_id,
        artifact_type=Artifact.Type.CHECKLIST,
        retrieve_context=retrieve_context,
        process_documents=process_documents,
        document_ids=document_ids,
        source_chat_id=source_chat_id,
        fragments=fragments,
    )
    checklist = checklist_repository.create(
        user_id=user_id,
        sections=sections,
        artifact_id=artifact.id,
        title=title,
        description=description,
        query=query,
    )
    return artifact, checklist


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
                    "position": idx,
                }
                for idx, it in enumerate(sorted_items)
            ],
        })
    return sections


class ChecklistService(ArtifactCrudService):
    repository = checklist_repository
    not_found_exc = ChecklistNotFoundException
    access_denied_exc = ChecklistAccessDeniedException
    log_model = "ArtifactChecklist"
    log_id_key = "checklist_id"
    perm_list = perms.LIST_CHECKLISTS
    perm_manage = perms.MANAGE_CHECKLISTS
    perm_get = perms.GET_CHECKLIST
    perm_update = perms.UPDATE_CHECKLIST
    perm_export = perms.EXPORT_CHECKLIST
    perm_manage_export = perms.MANAGE_EXPORT_CHECKLIST
    perm_delete = perms.DELETE_CHECKLIST
    logger = logger

    def list_checklists(self, user: AuthenticatedUser, chat_id: int):
        return self._list_by_chat(user, chat_id)

    def list_all_checklists(self, user: AuthenticatedUser):
        return self._list_all(user)

    def get_checklist(self, user: AuthenticatedUser, checklist_id: int) -> ArtifactChecklist:
        return self._get(user, checklist_id)

    def get_own_checklist(self, user: AuthenticatedUser, checklist_id: int) -> ArtifactChecklist:
        return self._get_own(user, checklist_id)

    def get_checklist_admin_export(self, user: AuthenticatedUser, checklist_id: int) -> ArtifactChecklist:
        return self._get_admin_export(user, checklist_id)

    def delete_checklist(self, user: AuthenticatedUser, checklist_id: int) -> None:
        self._delete(user, checklist_id)

    @transaction.atomic
    def set_item_checked(
            self,
            user: AuthenticatedUser,
            checklist_id: int,
            item_id: int,
            is_checked: bool,
    ) -> ArtifactChecklistItem:
        """Toggle a checklist item's ``is_checked`` flag.

        Requires the ``UPDATE_CHECKLIST`` permission and ownership: the user must
        be the checklist's creator or an active contributor of its source chat.
        """
        AccessControl.require_permissions(user, frozenset({self.perm_update}))
        checklist = self.repository.get_by_id_for_update(checklist_id)
        if checklist is None:
            raise self.not_found_exc()
        self._assert_access(user.id, checklist, require_contributor=True)

        item = self.repository.get_item(checklist_id, item_id)
        if item is None:
            raise ChecklistItemNotFoundException()

        item = self.repository.set_item_checked(item, is_checked)
        self.logger.info(
            "ArtifactChecklistItem check toggled",
            extra={"user_id": user.id, self.log_id_key: checklist_id, "item_id": item_id, "is_checked": is_checked},
        )
        return item

    async def generate_checklist(
            self,
            user: AuthenticatedUser,
            message: str,
            chat_id: int,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> tuple[ArtifactChecklist, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_CHECKLIST_GENERATE}))

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
            async for event in llm_client.generate_checklist_stream_events(
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
        description = str(result_data.get("description", "")).strip()
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
            description=description,
            query=message,
            retrieve_context=retrieve_context,
            process_documents=process_documents,
            document_ids=document_ids or [],
            source_chat_id=chat_id,
            sections=sections,
            fragments=fragments,
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
