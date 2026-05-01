import logging

from app.application.services.document_summary_service.constants.summarization_strategy import SummarizationStrategy
from app.application.services.document_summary_service.document_summary_settings import DocumentSummaryServiceSettings
from app.application.services.document_summary_service.document_summary_state import DocumentSummaryState
from app.application.services.document_summary_service.exceptions.document_summary_service_exceptions import (
    DocumentSummaryServiceException,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)

logger = logging.getLogger(__name__)


class ContextDocumentSummaryProcessor:
    def __init__(
            self,
            document_summary_service_settings: DocumentSummaryServiceSettings,
            document_context_provider: DocumentContextProviderInterface,
    ) -> None:
        self._settings = document_summary_service_settings
        self._document_context_provider = document_context_provider

    async def run(self, document_summary_state: DocumentSummaryState) -> None:
        logger.debug(
            "Retrieving context fragments for document",
            extra={"document_ids": document_summary_state.document_ids},
        )
        try:
            result = await self._document_context_provider.retrieve_context_fragments_by_document(
                document_ids=document_summary_state.document_ids,
                authenticated_user=document_summary_state.authenticated_user,
            )
            document_summary_state.fragments = result.fragments
        except DocumentSummaryServiceException:
            raise
        except Exception as e:
            logger.exception(
                "Failed to retrieve context fragments",
                extra={"document_ids": document_summary_state.document_ids, "error_type": type(e).__name__},
            )
            raise DocumentSummaryServiceException(
                "Error retrieving context fragments from the document service"
            ) from e

        fragment_count = len(document_summary_state.fragments)
        document_summary_state.strategy = (
            SummarizationStrategy.map_reduce
            if fragment_count > self._settings.large_document_threshold
            else SummarizationStrategy.direct
        )
        logger.debug(
            "Fragments retrieved and strategy selected",
            extra={
                "document_ids": document_summary_state.document_ids,
                "fragment_count": fragment_count,
                "strategy": document_summary_state.strategy.value,
            },
        )
