import logging
from typing import Optional

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms

from apps.report.exceptions import ReportAccessDeniedException, ReportNotFoundException
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
    def create_report(
            self,
            user: AuthenticatedUser,
            type: str,
            title: Optional[str],
            content: str,
            mode: str,
            metadata: dict,
    ) -> Report:
        AccessControl.require_permissions(user, frozenset({perms.CREATE_REPORT}))
        effective_title = (title or "").strip() or _auto_title(type, content)
        report = report_repository.create(
            user_id=user.id,
            type=type,
            title=effective_title,
            content=content,
            mode=mode,
            metadata=metadata,
        )
        logger.info("Report created", extra={"user_id": user.id, "report_id": report.id, "type": type})
        return report

    def list_reports(
            self,
            user: AuthenticatedUser,
            report_type: Optional[str] = None,
    ):
        AccessControl.require_permissions(user, frozenset({perms.LIST_REPORTS}))
        return report_repository.list_by_user(user_id=user.id, report_type=report_type)

    def get_report(self, user: AuthenticatedUser, report_id: int) -> Report:
        AccessControl.require_permissions(user, frozenset({perms.GET_REPORT}))
        report = report_repository.get_by_id(report_id)
        if report is None:
            raise ReportNotFoundException()
        if report.created_by != user.id:
            raise ReportAccessDeniedException()
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


report_service = ReportService()
