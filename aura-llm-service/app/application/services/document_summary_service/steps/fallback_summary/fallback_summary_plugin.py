import logging

from app.application.services.document_summary_service.interfaces.document_summary_plugin_interface import (
    DocumentSummaryPlugin,
)
from app.application.services.document_summary_service.pipeline.document_summary_pipeline_resources import (
    DocumentSummaryPipelineResources,
)
from app.application.services.document_summary_service.pipeline.document_summary_pipeline_state import (
    DocumentSummaryPipelineState,
)
from app.application.services.document_summary_service.steps.fallback_summary.fallback_summary_prompt import (
    FALLBACK_SUMMARY_MESSAGE,
)

logger = logging.getLogger(__name__)


class FallbackSummaryPlugin(DocumentSummaryPlugin):
    @property
    def plugin_name(self) -> str:
        return "fallback_summary"

    def should_run(
            self,
            state: DocumentSummaryPipelineState,
            resources: DocumentSummaryPipelineResources,
    ) -> bool:
        return not state.summary

    async def run(
            self,
            state: DocumentSummaryPipelineState,
            resources: DocumentSummaryPipelineResources,
    ) -> None:
        logger.warning(
            "No summary was generated — applying fallback",
            extra={"document_id": state.document_id, "fragment_count": len(state.fragments)},
        )
        state.summary = FALLBACK_SUMMARY_MESSAGE
