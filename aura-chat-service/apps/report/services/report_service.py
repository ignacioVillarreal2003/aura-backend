import logging
from typing import Optional

from django.utils import timezone
from asgiref.sync import sync_to_async
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import ReportGenerateResult, llm_client

from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.message.models.chat_message import ChatMessage
from apps.message.repositories.message_repository import message_repository
from apps.report.exceptions import LLMServiceException, ReportAccessDeniedException, ReportNotFoundException
from apps.report.models import Report
from apps.report.repositories.report_repository import report_repository

logger = logging.getLogger(__name__)

_AUTO_TITLE_MAX_CHARS = 80


def _auto_title(report_type: str, content: str) -> str:
    first_line = content.strip().splitlines()[0] if content.strip() else ""
    first_line = first_line.lstrip("#").strip()
    if first_line and len(first_line) <= _AUTO_TITLE_MAX_CHARS:
        return first_line
    ts = timezone.now().strftime("%Y-%m-%d %H:%M")
    return f"{report_type} — {ts}"


def _assert_report_access(user_id: int, report: Report, *, require_contributor: bool = False) -> None:
    if report.created_by == user_id:
        return
    if report.source_chat_id is not None:
        checker = (
            membership_repository.is_active_contributor
            if require_contributor
            else membership_repository.is_active_member
        )
        if checker(report.source_chat_id, user_id):
            return
    raise ReportAccessDeniedException()


class ReportService:
    def list_reports(
            self,
            user: AuthenticatedUser,
            report_type: Optional[str] = None,
            chat_id: Optional[int] = None,
    ):
        AccessControl.require_permissions(user, frozenset({perms.LIST_REPORTS}))
        if chat_id is not None:
            if chat_repository.get_by_id(chat_id) is None:
                raise ChatNotFoundException()
            if not membership_repository.is_active_member(chat_id, user.id):
                raise ChatAccessDeniedException()
            # Any active member of the chat sees every report in it, not only their own.
            return report_repository.list_by_chat(source_chat_id=chat_id, report_type=report_type)
        return report_repository.list_by_user(user_id=user.id, report_type=report_type)

    def list_all_reports(
            self,
            user: AuthenticatedUser,
            report_type: Optional[str] = None,
    ):
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_REPORTS}))
        return report_repository.list_all(report_type=report_type)

    def get_report(self, user: AuthenticatedUser, report_id: int) -> Report:
        AccessControl.require_permissions(user, frozenset({perms.GET_REPORT}))
        report = report_repository.get_by_id(report_id)
        if report is None:
            raise ReportNotFoundException()
        _assert_report_access(user.id, report)
        return report

    def get_own_report(self, user: AuthenticatedUser, report_id: int) -> Report:
        AccessControl.require_permissions(user, frozenset({perms.EXPORT_REPORT}))
        report = report_repository.get_by_id(report_id)
        if report is None:
            raise ReportNotFoundException()
        _assert_report_access(user.id, report)
        return report

    def get_report_admin_export(self, user: AuthenticatedUser, report_id: int) -> Report:
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_EXPORT_REPORT}))
        report = report_repository.get_by_id(report_id)
        if report is None:
            raise ReportNotFoundException()
        return report

    def update_report(
            self,
            user: AuthenticatedUser,
            report_id: int,
            title: Optional[str] = None,
            content: Optional[str] = None,
    ) -> Report:
        AccessControl.require_permissions(user, frozenset({perms.UPDATE_REPORT}))
        report = report_repository.get_by_id(report_id)
        if report is None:
            raise ReportNotFoundException()
        _assert_report_access(user.id, report, require_contributor=True)
        return report_repository.update(report, updated_by=user.id, title=title, content=content)

    def delete_report(self, user: AuthenticatedUser, report_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({perms.DELETE_REPORT}))
        report = report_repository.get_by_id(report_id)
        if report is None:
            raise ReportNotFoundException()
        _assert_report_access(user.id, report, require_contributor=True)
        report_repository.soft_delete(report, deleted_by=user.id)
        logger.info("Report deleted", extra={"user_id": user.id, "report_id": report_id})

    async def generate_report(
            self,
            user: AuthenticatedUser,
            report_type: str,
            message: str,
            mode: str,
            chat_id: Optional[int] = None,
    ) -> tuple[Report, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_REPORT_GENERATE}))

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
            result: ReportGenerateResult = await llm_client.generate_report(
                messages=messages,
                mode=mode,
                report_type=report_type,
                user=user,
                chat_id=chat_id,
            )
        except HttpClientException as e:
            logger.error(
                "LLM report-generate failed: %s",
                str(e),
                extra={"user_id": user.id, "report_type": report_type, "status_code": e.status_code},
                exc_info=True,
            )
            raise LLMServiceException() from e

        if not result.content or not result.content.strip():
            logger.error("LLM returned empty content for report", extra={"user_id": user.id, "report_type": report_type})
            raise LLMServiceException()

        report = await sync_to_async(report_repository.create)(
            user_id=user.id,
            type=result.report_type,
            title=_auto_title(result.report_type, result.content),
            content=result.content,
            mode=mode,
            source_chat_id=chat_id,
        )
        logger.info(
            "Report generated and saved",
            extra={"user_id": user.id, "report_id": report.id, "type": result.report_type, "source_chat_id": chat_id},
        )
        return report, result.messages, result.fragments


report_service = ReportService()
