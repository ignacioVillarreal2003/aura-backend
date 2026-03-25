import logging

from app.application.services.document_question_service.pipeline.document_question_pipeline_resources import (
    DocumentQuestionPipelineResources,
)
from app.application.services.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState,
)
from app.application.services.document_question_service.interfaces.document_question_plugin_interface import (
    DocumentQuestionPlugin,
)
from app.application.services.document_question_service.exceptions.document_question_service_exceptions import (
    DocumentQuestionServiceException,
)

logger = logging.getLogger(__name__)


class RetrieveContextPlugin(DocumentQuestionPlugin):
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
        query = state.effective_query or state.current_message.content
        try:
            state.retrieved_fragments = await resources.document_context_provider.retrieve_context_fragments_by_question(
                question=query,
                max_context_fragments=resources.settings.max_context_fragments,
                authorization=state.authorization,
            )
            logger.debug(
                "Context fragments retrieved",
                extra={"fragment_count": len(state.retrieved_fragments)},
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
