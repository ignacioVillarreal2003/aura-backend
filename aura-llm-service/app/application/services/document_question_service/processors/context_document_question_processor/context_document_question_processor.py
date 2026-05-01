import logging
from typing import Optional

from app.application.services.document_question_service.document_question_state import DocumentQuestionState
from app.application.services.document_question_service.exceptions.document_question_service_exceptions import (
    DocumentQuestionServiceException,
)
from app.application.services.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)

logger = logging.getLogger(__name__)


class ContextDocumentQuestionProcessor:
    def __init__(
            self,
            document_question_service_settings: DocumentQuestionServiceSettings,
            document_context_provider: DocumentContextProviderInterface,
    ) -> None:
        self._settings = document_question_service_settings
        self._document_context_provider = document_context_provider

    async def run(self, document_question_state: DocumentQuestionState) -> None:
        effective_question = document_question_state.base_question or document_question_state.current_message.content

        keyword_question: Optional[str] = None
        if self._settings.use_keywords and document_question_state.keyword_question:
            keyword_question = document_question_state.keyword_question

        try:
            fragments = await self._document_context_provider.retrieve_context_fragments_by_question(
                question=effective_question,
                question_max_fragments=self._settings.question_max_fragments,
                authenticated_user=document_question_state.authenticated_user,
                use_keywords=self._settings.use_keywords,
                keywords=document_question_state.keyword_question,
                keywords_max_fragments=self._settings.keywords_max_fragments,
                use_rerank=self._settings.use_rerank,
                rerank_max_fragments=self._settings.rerank_max_fragments
            )
            document_question_state.fragments = fragments.fragments
            logger.debug(
                "Context fragments retrieved",
                extra={
                    "fragment_count": len(fragments.fragments),
                    "question_max_fragments": self._settings.question_max_fragments,
                    "keywords_max_fragments": self._settings.keywords_max_fragments,
                    "use_rerank": self._settings.use_rerank,
                    "has_keywords": bool(keyword_question)
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
