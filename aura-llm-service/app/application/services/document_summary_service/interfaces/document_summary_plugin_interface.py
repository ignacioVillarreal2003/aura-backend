from abc import ABC, abstractmethod

from app.application.services.document_summary_service.pipeline.document_summary_pipeline_resources import (
    DocumentSummaryPipelineResources,
)
from app.application.services.document_summary_service.pipeline.document_summary_pipeline_state import (
    DocumentSummaryPipelineState,
)


class DocumentSummaryPlugin(ABC):
    @property
    @abstractmethod
    def plugin_name(self) -> str:
        pass

    @abstractmethod
    def should_run(
            self,
            state: DocumentSummaryPipelineState,
            resources: DocumentSummaryPipelineResources,
    ) -> bool:
        pass

    @abstractmethod
    async def run(
            self,
            state: DocumentSummaryPipelineState,
            resources: DocumentSummaryPipelineResources,
    ) -> None:
        pass
