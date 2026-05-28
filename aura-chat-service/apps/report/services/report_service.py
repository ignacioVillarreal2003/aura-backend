import logging
from typing import Optional

from asgiref.sync import sync_to_async
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import ReportGenerateResult, llm_client

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
    from django.utils import timezone
    ts = timezone.now().strftime("%Y-%m-%d %H:%M")
    return f"{report_type} — {ts}"


class ReportService:
    def list_reports(
            self,
            user: AuthenticatedUser,
            report_type: Optional[str] = None,
    ):
        AccessControl.require_permissions(user, frozenset({perms.LIST_REPORTS}))
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
        return report

    def get_own_report(self, user: AuthenticatedUser, report_id: int) -> Report:
        AccessControl.require_permissions(user, frozenset({perms.EXPORT_REPORT}))
        report = report_repository.get_by_id(report_id)
        if report is None:
            raise ReportNotFoundException()
        if report.created_by != user.id:
            raise ReportAccessDeniedException()
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
        if report.created_by != user.id:
            raise ReportAccessDeniedException()
        return report_repository.update(report, title=title, content=content)

    def delete_report(self, user: AuthenticatedUser, report_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({perms.DELETE_REPORT}))
        report = report_repository.get_by_id(report_id)
        if report is None:
            raise ReportNotFoundException()
        if report.created_by != user.id:
            raise ReportAccessDeniedException()
        report_repository.soft_delete(report, deleted_by=user.id)
        logger.info("Report deleted", extra={"user_id": user.id, "report_id": report_id})

    async def generate_report(
            self,
            user: AuthenticatedUser,
            report_type: str,
            message: str,
            mode: str,
    ) -> tuple[Report, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_REPORT_GENERATE}))
        messages = [{"role": "human", "content": message}]
        try:
            result: ReportGenerateResult = await llm_client.generate_report(
                messages=messages,
                mode=mode,
                report_type=report_type,
                user=user,
            )
        except HttpClientException as e:
            logger.error(
                "LLM report-generate failed: %s",
                str(e),
                extra={"user_id": user.id, "report_type": report_type, "status_code": e.status_code},
                exc_info=True,
            )
            raise LLMServiceException() from e

        report = await sync_to_async(report_repository.create)(
            user_id=user.id,
            type=result.report_type,
            title=_auto_title(result.report_type, result.content),
            content=result.content,
            mode=mode,
            metadata={},
        )
        logger.info(
            "Report generated and saved",
            extra={"user_id": user.id, "report_id": report.id, "type": result.report_type},
        )
        return report, result.messages, result.fragments


report_service = ReportService()
