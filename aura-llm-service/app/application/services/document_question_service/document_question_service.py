import logging
from typing import List, Optional
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable

from app.application.exceptions.app_exceptions import ValidationError
from app.application.llm_facade.exceptions.llm_facade_exceptions import LLMInvocationError
from app.application.llm_facade.interfaces.llm_facade_interface import LLMFacadeInterface
from app.application.services.document_question_service.document_question_configuration import (
    DocumentQuestionConfiguration
)
from app.application.services.document_question_service.document_question_message_builder import (
    DocumentQuestionMessageBuilder
)
from app.application.services.document_question_service.document_question_request_validator import (
    DocumentQuestionRequestValidator
)
from app.application.services.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface
)
from app.infrastructure.providers.exceptions.context_provider_exception import ContextRetrievalByQuestionError
from app.application.services.document_question_service.exceptions.document_question_service_exceptions import DocumentQuestionServiceError
from app.domain.dtos.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question_response import DocumentQuestionResponse
from app.domain.dtos.message import Message
from app.infrastructure.providers.interfaces.context_provider_interface import ContextProviderInterface

logger = logging.getLogger(__name__)


class DocumentQuestionService(DocumentQuestionServiceInterface):
    def __init__(self,
                 llm_facade: LLMFacadeInterface,
                 context_provider: ContextProviderInterface,
                 configuration: Optional[DocumentQuestionConfiguration] = None) -> None:
        self._llm_facade = llm_facade
        self._context_provider = context_provider
        self._configuration = configuration or DocumentQuestionConfiguration()

        self._validator = DocumentQuestionRequestValidator(self._configuration)
        self._message_builder = DocumentQuestionMessageBuilder()

        self._llm: Optional[Runnable] = None

        logger.info(
            "DocumentQuestionService initialized",
            extra={
                "max_fragments": self._configuration.max_fragments,
                "max_question_length": self._configuration.max_question_length,
                "max_history_count": self._configuration.max_history_count
            }
        )

    @classmethod
    def with_defaults(cls,
                      llm_facade: LLMFacadeInterface,
                      context_provider: ContextProviderInterface,
                      max_fragments: int = 3,
                      max_question_length: int = 1000,
                      max_history_count: int = 3,
                      system_prompt: Optional[str] = None) -> "DocumentQuestionService":
        configuration = DocumentQuestionConfiguration(
            max_fragments=max_fragments,
            max_question_length=max_question_length,
            max_history_count=max_history_count,
            system_prompt=system_prompt
        )

        return cls(
            llm_facade=llm_facade,
            context_provider=context_provider,
            configuration=configuration
        )

    async def execute_document_question(self,
                                        document_question_request: DocumentQuestionRequest) -> DocumentQuestionResponse:
        self._validator.validate_request(document_question_request)

        logger.info(
            "Executing document question",
            extra={
                "question_preview": document_question_request.question[:100],
                "has_history": document_question_request.messages is not None
            }
        )

        try:
            await self._ensure_llm_initialized()

            fragments = await self._retrieve_context(
                document_question_request.question
            )

            llm_input = self._build_llm_input(
                fragments=fragments,
                messages=document_question_request.messages or [],
                question=document_question_request.question
            )

            answer = await self._invoke_llm(llm_input)

            logger.info(
                "Document question executed successfully",
                extra={
                    "question_preview": document_question_request.question[:100],
                    "answer_length": len(answer),
                    "fragments_used": len(fragments)
                }
            )

            return DocumentQuestionResponse(answer=answer)

        except (ValidationError, ContextRetrievalByQuestionError, LLMInvocationError):
            raise

        except Exception as e:
            logger.exception(
                "Unexpected error during document question execution",
                extra={
                    "error_type": type(e).__name__,
                    "question_preview": document_question_request.question[:100]
                }
            )
            raise DocumentQuestionServiceError("Unexpected internal error executing document question") from e

    async def _ensure_llm_initialized(self) -> None:
        if self._llm is not None:
            return

        try:
            self._llm = await self._llm_facade.get_llm_base()

            logger.debug("LLM initialized for DocumentQuestionService")

        except Exception as e:
            logger.exception("Failed to initialize LLM")
            raise DocumentQuestionServiceError("Failed to initialize LLM for document questions") from e

    async def _retrieve_context(self,
                                question: str) -> List[str]:
        logger.debug(
            "Retrieving context fragments",
            extra={
                "question_preview": question[:100],
                "max_fragments": self._configuration.max_fragments
            }
        )

        fragments_sequence = await self._context_provider.retrieve_fragments_by_question(
            question=question,
            max_fragments=self._configuration.max_fragments
        )

        fragments = list(fragments_sequence)

        logger.debug(
            f"Retrieved {len(fragments)} context fragments",
            extra={
                "fragments_count": len(fragments)
            }
        )

        return fragments

    def _build_llm_input(self,
                         fragments: List[str],
                         messages: List[Message],
                         question: str) -> List[BaseMessage]:
        return self._message_builder.build_complete_input(
            system_prompt=self._configuration.effective_system_prompt,
            fragments=fragments,
            messages=messages,
            question=question
        )

    async def _invoke_llm(self,
                          llm_input: List[BaseMessage]) -> str:
        if self._llm is None:
            raise DocumentQuestionServiceError("LLM not initialized, cannot invoke")

        logger.debug(
            "Invoking LLM",
            extra={
                "input_messages_count": len(llm_input)
            }
        )

        answer = await self._llm_facade.call_llm_text(
            llm=self._llm,
            llm_input=llm_input
        )

        return answer

    @property
    def configuration(self) -> DocumentQuestionConfiguration:
        return self._configuration

    @property
    def is_llm_initialized(self) -> bool:
        return self._llm is not None
