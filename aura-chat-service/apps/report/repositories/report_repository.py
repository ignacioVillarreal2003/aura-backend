import logging
from typing import Optional

from apps.report.models import Report

logger = logging.getLogger(__name__)


class ReportRepository:
    def create(
            self,
            *,
            user_id: int,
            type: str,
            title: str,
            content: str,
            mode: str,
            metadata: dict,
    ) -> Report:
        return Report.objects.create(
            created_by=user_id,
            type=type,
            title=title,
            content=content,
            mode=mode,
            metadata=metadata,
        )

    def get_by_id(self, report_id: int) -> Optional[Report]:
        return Report.objects.filter(id=report_id).first()

    def list_by_user(self, user_id: int, report_type: Optional[str] = None):
        qs = Report.objects.filter(created_by=user_id)
        if report_type:
            qs = qs.filter(type=report_type)
        return qs

    def update(self, report: Report, *, title: Optional[str] = None, content: Optional[str] = None) -> Report:
        update_fields = []
        if title is not None:
            report.title = title
            update_fields.append("title")
        if content is not None:
            report.content = content
            update_fields.append("content")
        if update_fields:
            report.save(update_fields=update_fields)
        return report

    def soft_delete(self, report: Report, deleted_by: int) -> None:
        report.delete(deleted_by=deleted_by)


report_repository = ReportRepository()
