import logging
from typing import List, Optional

from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable

from app.application.services.document_question_service.document_question_configuration import (
    DocumentQuestionConfiguration
)
from app.application.services.document_question_service.document_question_prompt_builder import \
    DocumentQuestionPromptBuilder
from app.application.services.document_question_service.document_question_request_validator import \
    DocumentQuestionRequestValidator
from app.application.services.document_question_service.exceptions.document_question_service_exceptions import \
    DocumentQuestionServiceError
from app.application.services.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface
)
from app.domain.dtos.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question_response import DocumentQuestionResponse
from app.domain.dtos.message import Message
from app.infrastructure.context_provider.exceptions.context_provider_exception import ContextRetrievalByQuestionError
from app.infrastructure.context_provider.interfaces.context_provider_interface import (
    ContextProviderInterface
)
from app.infrastructure.llm_facade.exceptions.llm_facade_exceptions import LLMInvocationError
from app.infrastructure.llm_facade.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)


class DocumentQuestionService(DocumentQuestionServiceInterface):
    def __init__(self,
                 ollama_llm_facade: OllamaLLMFacadeInterface,
                 context_provider: ContextProviderInterface,
                 configuration: Optional[DocumentQuestionConfiguration] = None) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._context_provider = context_provider
        self._configuration = configuration or DocumentQuestionConfiguration()

        self._request_validator = DocumentQuestionRequestValidator(self._configuration)
        self._prompt_builder = DocumentQuestionPromptBuilder()

        self._llm: Optional[Runnable] = None

        logger.info("DocumentQuestionService initialized")

    @classmethod
    def with_defaults(cls,
                      ollama_llm_facade: OllamaLLMFacadeInterface,
                      context_provider: ContextProviderInterface,
                      fragments_count: Optional[int] = None,
                      question_length: Optional[int] = None,
                      history_count: Optional[int] = None,
                      custom_system_prompt: Optional[str] = None) -> "DocumentQuestionService":
        configuration = DocumentQuestionConfiguration(
            fragments_count=fragments_count,
            question_length=question_length,
            history_count=history_count,
            custom_system_prompt=custom_system_prompt
        )

        return cls(
            ollama_llm_facade=ollama_llm_facade,
            context_provider=context_provider,
            configuration=configuration
        )

    async def execute_document_question(self,
                                        request_body: DocumentQuestionRequest) -> DocumentQuestionResponse:
        logger.info(
            "Executing document question",
            extra={
                "question": request_body.question,
                "messages_count": len(request_body.messages)
            }
        )

        self._request_validator.validate_request(request_body)

        fragments = await self.retrieve_fragments_by_question(request_body.question)

        answer = await self.answer_question(
            question=request_body.question,
            messages=request_body.messages,
            fragments=fragments
        )

        logger.info(
            "Document question executed successfully",
            extra={
                "question": request_body.question,
                "messages_count": len(request_body.messages)
            }
        )

        return DocumentQuestionResponse(
            answer=answer
        )

    async def answer_question(self,
                              question: str,
                              messages: Optional[list[Message]] = None,
                              fragments: Optional[List[str]] = None) -> str:
        logger.info(
            "Answering document question",
            extra={
                "question": question,
                "messages": messages,
                "fragments": fragments
            }
        )

        try:
            await self._ensure_llm_ready()

            prompt = self._build_prompt(
                question=question,
                fragments=fragments,
                history=messages or []
            )

            answer = await self._invoke_llm(prompt)

            logger.info(
                "Question answered successfully",
                extra={
                    "question_length": len(question),
                    "answer_length": len(answer),
                    "fragments_used": len(fragments)
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

    async def retrieve_fragments_by_question(self,
                                             question: str,
                                             fragments_count: Optional[int] = None) -> List[str]:
        logger.info(
            "Retrieving fragments by question",
            extra={
                "question": question,
                "fragments_count": fragments_count
            }
        )

        try:
            fragments = await self._context_provider.retrieve_fragments_by_question(
                question=question,
                fragments_count=fragments_count
            )

            logger.info(
                "Fragments retrieved successfully",
                extra={
                    "fragments": fragments,
                    "question": question,
                    "fragments_count": fragments_count
                }
            )

            return fragments

        except ContextRetrievalByQuestionError:
            logger.error(
                "Failed to retrieve context fragments",
                extra={
                    "question": question,
                    "fragments_count": fragments_count
                }
            )
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error retrieving fragments by question",
                extra={
                    "error_type": type(e).__name__,
                    "question": question,
                    "fragments_count": fragments_count
                }
            )
            raise DocumentQuestionServiceError("Error al recuperar fragmentos del documento") from e

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
                      fragments: List[str],
                      history: List[Message]) -> List[BaseMessage]:
        return self._prompt_builder.build_complete_prompt(
            system_prompt=self._configuration.system_prompt,
            fragments=fragments,
            messages=history,
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
