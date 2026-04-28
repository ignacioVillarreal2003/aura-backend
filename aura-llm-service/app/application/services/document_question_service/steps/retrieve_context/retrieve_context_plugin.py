import logging
from typing import Optional

from app.application.services.document_question_service.pipeline.document_question_pipeline_resources import (
    DocumentQuestionPipelineResources
)
from app.application.services.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState
)
from app.application.services.document_question_service.interfaces.document_question_plugin_interface import (
    DocumentQuestionPlugin
)
from app.application.services.document_question_service.exceptions.document_question_service_exceptions import (
    DocumentQuestionServiceException
)
from app.application.services.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings,
)

logger = logging.getLogger(__name__)


class RetrieveContextPlugin(DocumentQuestionPlugin):
    def __init__(self, settings: Optional[DocumentQuestionServiceSettings] = None) -> None:
        self._settings = settings or DocumentQuestionServiceSettings()

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
            resources: DocumentQuestionPipelineResources
    ) -> None:
        question_with_history = state.question_with_history or state.current_message.content
        keywords: Optional[str] = None
        if self._settings.use_keywords and state.retrieval_keywords:
            keywords = state.retrieval_keywords

        try:
            fragments = await resources.document_context_provider.retrieve_context_fragments_by_question(
                question=question_with_history,
                question_max_fragments=self._settings.question_max_fragments,
                authenticated_user=state.authenticated_user,
                use_keywords=self._settings.use_keywords,
                keywords=keywords,
                keywords_max_fragments=self._settings.keywords_max_fragments,
                use_rerank=self._settings.use_rerank,
                rerank_max_fragments=self._settings.rerank_max_fragments
            )
            state.retrieved_fragments = fragments.fragments
            logger.debug(
                "Context fragments retrieved",
                extra={
                    "fragment_count": len(fragments.fragments),
                    "question_max_fragments": self._settings.question_max_fragments,
                    "keywords_max_fragments": self._settings.keywords_max_fragments,
                    "use_rerank": self._settings.use_rerank,
                    "has_keywords": bool(keywords)
                }
            )
        except DocumentQuestionServiceException:
            raise
        except Exception as e:
            logger.exception(
                "Failed to retrieve context fragments",
                extra={
                    "error_type": type(e).__name__
                }
            )
            raise DocumentQuestionServiceException(
                "Error retrieving context fragments from the document service"
            ) from e
