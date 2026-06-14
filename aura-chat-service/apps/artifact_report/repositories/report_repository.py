import logging
from typing import Optional

from apps.artifact_report.models import ArtifactReport

logger = logging.getLogger(__name__)


class ReportRepository:
    def create(
            self,
            *,
            user_id: int,
            type: str,
            content: str,
            artifact_id: int,
            title: str = "",
            description: str = "",
            query: str = "",
    ) -> ArtifactReport:
        return ArtifactReport.objects.create(
            created_by=user_id,
            type=type,
            content=content,
            artifact_id=artifact_id,
            title=title,
            description=description,
            query=query,
        )

    def get_by_id(self, report_id: int) -> Optional[ArtifactReport]:
        return ArtifactReport.objects.select_related("artifact").filter(id=report_id).first()

    def get_by_id_for_update(self, report_id: int) -> Optional[ArtifactReport]:
        return ArtifactReport.objects.select_for_update().select_related("artifact").filter(id=report_id).first()

    def list_by_user(
            self,
            user_id: int,
            report_type: Optional[str] = None,
    ):
        qs = ArtifactReport.objects.select_related("artifact").filter(created_by=user_id)
        if report_type:
            qs = qs.filter(type=report_type)
        return qs

    def list_by_chat(
            self,
            source_chat_id: int,
            report_type: Optional[str] = None,
    ):
        qs = ArtifactReport.objects.select_related("artifact").filter(
            artifact__source_chat_id=source_chat_id
        )
        if report_type:
            qs = qs.filter(type=report_type)
        return qs

    def list_all(self, report_type: Optional[str] = None):
        qs = ArtifactReport.objects.select_related("artifact").all()
        if report_type:
            qs = qs.filter(type=report_type)
        return qs

    def soft_delete(self, report: ArtifactReport, deleted_by: int) -> None:
        report.delete(deleted_by=deleted_by)


report_repository = ReportRepository()
