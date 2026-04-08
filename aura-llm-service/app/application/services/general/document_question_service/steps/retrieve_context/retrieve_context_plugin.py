import logging
from typing import Optional

from app.application.services.general.document_question_service.pipeline.document_question_pipeline_resources import (
    DocumentQuestionPipelineResources,
)
from app.application.services.general.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState,
)
from app.application.services.general.document_question_service.interfaces.document_question_plugin_interface import (
    DocumentQuestionPlugin,
)
from app.application.services.general.document_question_service.exceptions.document_question_service_exceptions import (
    DocumentQuestionServiceException,
)
from app.application.services.general.document_question_service.steps.retrieve_context.retrieve_context_settings import (
    RetrieveContextSettings,
)

logger = logging.getLogger(__name__)


class RetrieveContextPlugin(DocumentQuestionPlugin):
    def __init__(self, retrieve_context_settings: Optional[RetrieveContextSettings] = None) -> None:
        self._settings = retrieve_context_settings or RetrieveContextSettings()

    @property
    def plugin_name(self) -> str:
        return "retrieve_context"

    def should_run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> bool:
        return True

    async def run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> None:
        query = state.retrieval_query or state.current_message.content

        try:
            fragments = await resources.document_context_provider.retrieve_context_fragments_by_question(
                question=query,
                max_fragments=self._settings.max_fragments,
                authenticated_user=state.authenticated_user,
            )
            state.retrieved_fragments = fragments.fragments
            logger.debug(
                "Context fragments retrieved",
                extra={"fragment_count": len(fragments.fragments), "max_fragments": self._settings.max_fragments},
            )
        except DocumentQuestionServiceException:
            raise
        except Exception as e:
            logger.exception(
                "Failed to retrieve context fragments",
                extra={"error_type": type(e).__name__},
            )
            raise DocumentQuestionServiceException(
                "Error retrieving context fragments from the document service"
            ) from e
