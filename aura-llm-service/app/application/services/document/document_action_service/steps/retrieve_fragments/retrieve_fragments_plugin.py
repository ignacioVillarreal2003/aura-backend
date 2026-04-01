import asyncio
import logging
from typing import Optional

from app.application.services.document.document_action_service.constants.processing_strategy import ProcessingStrategy
from app.application.services.document.document_action_service.exceptions.document_action_service_exceptions import (
    DocumentActionServiceException,
)
from app.application.services.document.document_action_service.interfaces.document_action_plugin_interface import (
    DocumentActionPlugin,
)
from app.application.services.document.document_action_service.pipeline.document_action_pipeline_resources import (
    DocumentActionPipelineResources,
)
from app.application.services.document.document_action_service.pipeline.document_action_pipeline_state import (
    DocumentActionPipelineState,
)
from app.application.services.document.document_action_service.steps.retrieve_fragments.retrieve_fragments_settings import (
    RetrieveActionFragmentsSettings,
)
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse

logger = logging.getLogger(__name__)


class RetrieveFragmentsPlugin(DocumentActionPlugin):
    def __init__(
            self,
            retrieve_fragments_settings: Optional[RetrieveActionFragmentsSettings] = None,
    ) -> None:
        self._settings = retrieve_fragments_settings or RetrieveActionFragmentsSettings()

    @property
    def plugin_name(self) -> str:
        return "retrieve_fragments"

    def should_run(
            self,
            state: DocumentActionPipelineState,
            resources: DocumentActionPipelineResources,
    ) -> bool:
        return True

    async def run(
            self,
            state: DocumentActionPipelineState,
            resources: DocumentActionPipelineResources,
    ) -> None:
        logger.debug(
            "Retrieving fragments for multiple documents",
            extra={"document_ids": state.document_ids},
        )

        try:
            results = await asyncio.gather(
                *[
                    resources.document_context_provider.retrieve_context_fragments_by_document(
                        document_id=doc_id,
                        authenticated_user=state.authenticated_user,
                    )
                    for doc_id in state.document_ids
                ],
                return_exceptions=True,
            )
        except Exception as e:
            logger.exception("Failed to retrieve context fragments")
            raise DocumentActionServiceException(
                "Error retrieving context fragments from the document service"
            ) from e

        fragments_by_document: dict[int, list[FragmentResponse]] = {}
        all_fragments: list[FragmentResponse] = []

        for doc_id, result in zip(state.document_ids, results):
            if isinstance(result, Exception):
                logger.warning(
                    "Failed to retrieve fragments for document",
                    extra={"document_id": doc_id, "error_type": type(result).__name__},
                )
                fragments_by_document[doc_id] = []
                continue

            doc_fragments = result.context_fragments
            fragments_by_document[doc_id] = doc_fragments
            all_fragments.extend(doc_fragments)

        if not all_fragments:
            logger.warning(
                "No fragments retrieved for any document",
                extra={"document_ids": state.document_ids},
            )

        state.fragments_by_document = fragments_by_document
        state.all_fragments = all_fragments

        total = len(all_fragments)
        state.strategy = (
            ProcessingStrategy.map_reduce
            if total > self._settings.large_document_threshold
            else ProcessingStrategy.direct
        )

        logger.debug(
            "Fragments retrieved and strategy selected",
            extra={
                "total_fragments": total,
                "documents_with_fragments": sum(1 for v in fragments_by_document.values() if v),
                "strategy": state.strategy.value,
            },
        )
