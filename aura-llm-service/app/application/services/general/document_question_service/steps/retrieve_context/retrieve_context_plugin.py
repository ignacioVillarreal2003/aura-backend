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
        full_question = state.current_message.content
        search_keywords: Optional[str] = None
        if self._settings.send_search_keywords and state.retrieval_query:
            search_keywords = state.retrieval_query

        try:
            fragments = await resources.document_context_provider.retrieve_context_fragments_by_question(
                question=full_question,
                max_fragments=self._settings.max_fragments,
                authenticated_user=state.authenticated_user,
                search_keywords=search_keywords,
                use_rerank=self._settings.use_rerank,
                rerank_final_fragments=self._settings.rerank_final_fragments,
            )
            state.retrieved_fragments = fragments.fragments
            logger.debug(
                "Context fragments retrieved",
                extra={
                    "fragment_count": len(fragments.fragments),
                    "max_fragments": self._settings.max_fragments,
                    "use_rerank": self._settings.use_rerank,
                    "has_search_keywords": bool(search_keywords),
                },
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
