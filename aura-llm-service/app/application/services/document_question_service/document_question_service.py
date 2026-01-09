import logging
from typing import List, Optional
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable

from app.application.services.document_question_service.document_question_configuration import (
    DocumentQuestionConfiguration
)
from app.application.services.document_question_service.document_question_prompt_builder import (
    DocumentQuestionPromptBuilder
)
from app.application.services.document_question_service.document_question_request_validator import (
    DocumentQuestionRequestValidator
)
from app.application.services.document_question_service.exceptions.document_question_service_exceptions import (
    DocumentQuestionServiceError
)
from app.application.services.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface
)
from app.domain.dtos.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question_response import DocumentQuestionResponse
from app.domain.dtos.message import Message
from app.infrastructure.document_context_provider.exceptions.context_provider_exception import ContextRetrievalByQuestionError
from app.infrastructure.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface
)
from app.infrastructure.llm_facade.exceptions.llm_facade_exceptions import LLMInvocationError
from app.infrastructure.llm_facade.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)


class DocumentQuestionService(DocumentQuestionServiceInterface):
    def __init__(self,
                 ollama_llm_facade: OllamaLLMFacadeInterface,
                 document_context_provider: DocumentContextProviderInterface,
                 configuration: Optional[DocumentQuestionConfiguration] = None) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._document_context_provider = document_context_provider
        self._configuration = configuration or DocumentQuestionConfiguration()

        self._request_validator = DocumentQuestionRequestValidator(self._configuration)
        self._prompt_builder = DocumentQuestionPromptBuilder()

        self._llm: Optional[Runnable] = None

        logger.info("DocumentQuestionService initialized")

    @classmethod
    def with_defaults(cls,
                      ollama_llm_facade: OllamaLLMFacadeInterface,
                      document_context_provider: DocumentContextProviderInterface,
                      max_context_fragments_count: Optional[int] = None,
                      max_question_length: Optional[int] = None,
                      max_history_messages_count: Optional[int] = None,
                      custom_system_prompt: Optional[str] = None) -> "DocumentQuestionService":
        configuration = DocumentQuestionConfiguration(
            max_context_fragments_count=max_context_fragments_count,
            max_question_length=max_question_length,
            max_history_messages_count=max_history_messages_count,
            custom_system_prompt=custom_system_prompt
        )

        return cls(
            ollama_llm_facade=ollama_llm_facade,
            document_context_provider=document_context_provider,
            configuration=configuration
        )

    async def execute_document_question(self,
                                        request: DocumentQuestionRequest) -> DocumentQuestionResponse:
        logger.info(
            "Executing document question",
            extra={
                "question": request.question,
                "history_messages": request.history_messages
            }
        )

        self._request_validator.validate_request(request)

        context_fragments = await self.retrieve_context_fragments_by_question(request.question)

        answer = await self.answer_question(
            question=request.question,
            history_messages=request.history_messages,
            context_fragments=context_fragments
        )

        logger.info(
            "Document question executed successfully",
            extra={
                "question": request.question,
                "messages_count": len(request.messages)
            }
        )

        return DocumentQuestionResponse(
            answer=answer
        )

    async def retrieve_context_fragments_by_question(self,
                                                     question: str,
                                                     context_fragments_count: Optional[int] = None) -> List[str]:
        logger.info(
            "Retrieving context fragments by question",
            extra={
                "question": question,
                "context_fragments_count": context_fragments_count
            }
        )

        try:
            fragments = await self._document_context_provider.retrieve_context_fragments_by_question(
                question=question,
                context_fragments_count=context_fragments_count
            )

            logger.info(
                "Fragments retrieved successfully",
                extra={
                    "question": question,
                    "fragments": fragments,
                    "context_fragments_count": context_fragments_count
                }
            )

            return fragments

        except ContextRetrievalByQuestionError:
            logger.error(
                "Failed to retrieve context fragments",
                extra={
                    "question": question,
                    "context_fragments_count": context_fragments_count
                }
            )
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error retrieving fragments by question",
                extra={
                    "error_type": type(e).__name__,
                    "question": question,
                    "context_fragments_count": context_fragments_count
                }
            )
            raise DocumentQuestionServiceError("Error al recuperar fragmentos del documento") from e

    async def answer_question(self,
                              question: str,
                              history_messages: Optional[list[Message]] = None,
                              context_fragments: Optional[List[str]] = None) -> str:
        logger.info(
            "Answering document question",
            extra={
                "question": question,
                "history_messages": history_messages,
                "context_fragments": context_fragments
            }
        )

        try:
            await self._ensure_llm_ready()

            prompt = self._build_prompt(
                question=question,
                context_fragments=context_fragments,
                history_messages=history_messages or []
            )

            answer = await self._invoke_llm(prompt)

            logger.info(
                "Question answered successfully",
                extra={
                    "question": question,
                    "answer": answer
                }
            )

            return answer

        except (ContextRetrievalByQuestionError, LLMInvocationError):
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error answering question",
                extra={
                    "error_type": type(e).__name__,
                    "question_length": len(question)
                }
            )
            raise DocumentQuestionServiceError("Error inesperado al generar la respuesta") from e

    async def _ensure_llm_ready(self) -> None:
        if self._llm is not None:
            return

        logger.debug("Initializing LLM for DocumentQuestionUseCase")

        try:
            self._llm = await self._ollama_llm_facade.get_llm_base()
            logger.info("LLM initialized successfully")
        except Exception as e:
            logger.error(
                "Failed to initialize LLM",
                extra={
                    "error_type": type(e).__name__,
                    "error": str(e)
                },
                exc_info=True
            )
            raise DocumentQuestionServiceError("Error al inicializar el modelo de lenguaje") from e

    def _build_prompt(self,
                      question: str,
                      context_fragments: List[str],
                      history_messages: List[Message]) -> List[BaseMessage]:
        return self._prompt_builder.build_complete_prompt(
            system_prompt=self._configuration.system_prompt,
            context_fragments=context_fragments,
            history_messages=history_messages,
            question=question
        )

    async def _invoke_llm(self,
                          prompt: List[BaseMessage]) -> str:
        if self._llm is None:
            raise DocumentQuestionServiceError("LLM no inicializado, no se puede invocar")

        logger.debug(
            "Invoking LLM",
            extra={
                "prompt": prompt
            }
        )

        try:
            answer = await self._ollama_llm_facade.call_llm_text(
                llm=self._llm,
                llm_input=prompt
            )

            logger.debug(
                "LLM invocation successful",
                extra={
                    "answer_length": len(answer)
                }
            )

            return answer

        except LLMInvocationError:
            logger.error("LLM invocation failed")
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during LLM invocation",
                extra={
                    "error_type": type(e).__name__
                }
            )
            raise DocumentQuestionServiceError("Error al invocar el modelo de lenguaje") from e

    @property
    def configuration(self) -> DocumentQuestionConfiguration:
        return self._configuration

    @property
    def is_llm_initialized(self) -> bool:
        return self._llm is not None
