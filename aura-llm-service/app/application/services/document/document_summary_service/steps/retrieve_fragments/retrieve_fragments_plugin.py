import logging
from typing import Optional

from app.application.services.document.document_summary_service.constants.summarization_strategy import SummarizationStrategy
from app.application.services.document.document_summary_service.exceptions.document_summary_service_exceptions import (
    DocumentSummaryServiceException,
)
from app.application.services.document.document_summary_service.interfaces.document_summary_plugin_interface import (
    DocumentSummaryPlugin,
)
from app.application.services.document.document_summary_service.pipeline.document_summary_pipeline_resources import (
    DocumentSummaryPipelineResources,
)
from app.application.services.document.document_summary_service.pipeline.document_summary_pipeline_state import (
    DocumentSummaryPipelineState,
)
from app.application.services.document.document_summary_service.steps.retrieve_fragments.retrieve_fragments_settings import (
    RetrieveFragmentsSettings,
)

logger = logging.getLogger(__name__)


class RetrieveFragmentsPlugin(DocumentSummaryPlugin):
    def __init__(
            self,
            retrieve_fragments_settings: Optional[RetrieveFragmentsSettings] = None,
    ) -> None:
        self._settings = retrieve_fragments_settings or RetrieveFragmentsSettings()

    @property
    def plugin_name(self) -> str:
        return "retrieve_fragments"

    def should_run(
            self,
            state: DocumentSummaryPipelineState,
            resources: DocumentSummaryPipelineResources,
    ) -> bool:
        return True

    async def run(
            self,
            state: DocumentSummaryPipelineState,
            resources: DocumentSummaryPipelineResources,
    ) -> None:
        logger.debug(
            "Retrieving context fragments for document",
            extra={"document_id": state.document_id},
        )

        try:
            result = await resources.document_context_provider.retrieve_context_fragments_by_document(
                document_id=state.document_id,
                authenticated_user=state.authenticated_user,
            )
            state.fragments = result.context_fragments
        except DocumentSummaryServiceException:
            raise
        except Exception as e:
            logger.exception(
                "Failed to retrieve context fragments",
                extra={"document_id": state.document_id, "error_type": type(e).__name__},
            )
            raise DocumentSummaryServiceException(
                "Error retrieving context fragments from the document service"
            ) from e

        fragment_count = len(state.fragments)
        state.strategy = (
            SummarizationStrategy.map_reduce
            if fragment_count > self._settings.large_document_threshold
            else SummarizationStrategy.direct
        )

        logger.debug(
            "Fragments retrieved and strategy selected",
            extra={
                "document_id": state.document_id,
                "fragment_count": fragment_count,
                "strategy": state.strategy.value,
            },
        )
