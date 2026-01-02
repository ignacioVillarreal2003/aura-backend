import logging
from typing import List, Optional
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable

from app.application.exceptions.app_exceptions import ValidationError
from app.infrastructure.llm_facade.exceptions.llm_facade_exceptions import LLMInvocationError
from app.infrastructure.llm_facade.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.application.services.document_question_service.document_question_configuration import (
    DocumentQuestionConfiguration
)
from app.application.services.document_question_service.document_question_prompt_builder import (
    DocumentQuestionPromptBuilder
)
from app.application.services.document_question_service.document_question_request_validator import (
    DocumentQuestionRequestValidator
)
from app.application.services.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface
)
from app.application.services.document_question_service.exceptions.document_question_service_exceptions import (
    DocumentQuestionServiceError
)
from app.domain.dtos.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question_response import DocumentQuestionResponse
from app.domain.dtos.message import Message
from app.infrastructure.context_provider.exceptions.context_provider_exception import ContextRetrievalByQuestionError
from app.infrastructure.context_provider.interfaces.context_provider_interface import ContextProviderInterface

logger = logging.getLogger(__name__)


class DocumentQuestionService(DocumentQuestionServiceInterface):
    def __init__(self,
                 llm_facade: OllamaLLMFacadeInterface,
                 context_provider: ContextProviderInterface,
                 configuration: Optional[DocumentQuestionConfiguration] = None) -> None:
        self._llm_facade = llm_facade
        self._context_provider = context_provider
        self._configuration = configuration or DocumentQuestionConfiguration()

        self._validator = DocumentQuestionRequestValidator(self._configuration)
        self._prompt_builder = DocumentQuestionPromptBuilder()

        self._llm: Optional[Runnable] = None

        logger.info(
            "DocumentQuestionService initialized successfully",
            extra={
                "default_fragments_count": self._configuration.default_fragments_count,
                "default_question_length": self._configuration.default_question_length,
                "default_history_count": self._configuration.default_history_count
            }
        )

    @classmethod
    def with_defaults(cls,
                      llm_facade: OllamaLLMFacadeInterface,
                      context_provider: ContextProviderInterface,
                      fragments_count: int = 3,
                      question_length: int = 1000,
                      history_count: int = 3,
                      system_prompt: Optional[str] = None) -> "DocumentQuestionService":
        configuration = DocumentQuestionConfiguration(
            default_fragments_count=fragments_count,
            default_question_length=question_length,
            default_history_count=history_count,
            default_system_prompt=system_prompt
        )

        return cls(
            llm_facade=llm_facade,
            context_provider=context_provider,
            configuration=configuration
        )

    async def execute_document_question(self,
                                        request_body: DocumentQuestionRequest) -> DocumentQuestionResponse:
        self._validator.validate_request(request_body)

        logger.info(
            "Executing document question",
            extra={
                "question": request_body.question,
                "messages_count": len(request_body.messages) if request_body.messages else 0
            }
        )

        try:
            await self._ensure_llm_initialized()

            fragments = await self._retrieve_context(request_body.question)

            llm_input = self._build_llm_prompt(
                fragments=fragments,
                messages=request_body.messages or [],
                question=request_body.question
            )

            answer = await self._invoke_llm(llm_input)

            logger.info(
                "Document question executed successfully",
                extra={
                    "question": request_body.question,
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
                    "error_message": str(e),
                    "question": request_body.question
                }
            )
            raise DocumentQuestionServiceError(
                "Error inesperado al ejecutar la pregunta sobre el documento"
            ) from e

    async def retrieve_fragments_by_question(self,
                                             question: str,
                                             fragments_count: Optional[int] = None) -> List[str]:
        count = fragments_count or self._configuration.default_fragments_count
        
        logger.info(
            "Retrieving context fragments by question",
            extra={
                "question": question,
                "fragments_count": count
            }
        )

        try:
            fragments = await self._context_provider.retrieve_fragments_by_question(
                question=question,
                fragments_count=count
            )

            logger.info(
                "Context fragments retrieved successfully",
                extra={
                    "question": question,
                    "requested_fragments": count,
                    "retrieved_fragments": len(fragments)
                }
            )

            return fragments

        except ContextRetrievalByQuestionError:
            raise

        except Exception as e:
            logger.error(
                "Error retrieving context fragments",
                extra={
                    "question": question,
                    "fragments_count": count,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise DocumentQuestionServiceError(
                "Error al recuperar los fragmentos de contexto para la pregunta"
            ) from e

    async def _ensure_llm_initialized(self) -> None:
        if self._llm is not None:
            return

        logger.debug("Initializing LLM for DocumentQuestionService")

        try:
            self._llm = await self._llm_facade.get_llm_base()

            logger.info("LLM initialized successfully for DocumentQuestionService")

        except Exception as e:
            logger.error(
                "Failed to initialize LLM",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise DocumentQuestionServiceError(
                "Error al inicializar el LLM para preguntas sobre documentos"
            ) from e

    async def _retrieve_context(self,
                                question: str) -> List[str]:
        return await self.retrieve_fragments_by_question(
            question=question,
            fragments_count=self._configuration.default_fragments_count
        )

    def _build_llm_prompt(self,
                          fragments: List[str],
                          messages: List[Message],
                          question: str) -> List[BaseMessage]:
        logger.debug(
            "Building LLM prompt",
            extra={
                "fragments_count": len(fragments),
                "messages_count": len(messages),
                "question_length": len(question)
            }
        )

        return self._prompt_builder.build_complete_prompt(
            system_prompt=self._configuration.get_system_prompt,
            fragments=fragments,
            messages=messages,
            question=question
        )

    async def _invoke_llm(self,
                          llm_prompt: List[BaseMessage]) -> str:
        if self._llm is None:
            raise DocumentQuestionServiceError("LLM not initialized, cannot invoke")

        logger.debug(
            "Invoking LLM",
            extra={
                "prompt_messages_count": len(llm_prompt)
            }
        )

        try:
            answer = await self._llm_facade.call_llm_text(
                llm=self._llm,
                llm_input=llm_prompt
            )

            logger.debug(
                "LLM invocation successful",
                extra={
                    "answer_length": len(answer)
                }
            )

            return answer

        except LLMInvocationError:
            raise

        except Exception as e:
            logger.error(
                "Error invoking LLM",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise DocumentQuestionServiceError("Error al invocar el LLM") from e

    @property
    def configuration(self) -> DocumentQuestionConfiguration:
        return self._configuration

    @property
    def is_llm_initialized(self) -> bool:
        return self._llm is not None
