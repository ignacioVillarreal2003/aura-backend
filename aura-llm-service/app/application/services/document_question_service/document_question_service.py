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
from app.infrastructure.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface
)
from app.infrastructure.ollama_llm_facade.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

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
        self._llm_initialization_failed = False

        logger.info("DocumentQuestionService initialized")

    @classmethod
    def create(cls,
               ollama_llm_facade: OllamaLLMFacadeInterface,
               document_context_provider: DocumentContextProviderInterface,
               max_context_fragments_count: Optional[int] = None,
               max_question_length: Optional[int] = None,
               max_history_messages_count: Optional[int] = None,
               custom_system_prompt: Optional[str] = None) -> "DocumentQuestionService":
        config_kwargs = {}

        if max_context_fragments_count is not None:
            config_kwargs['max_context_fragments_count'] = max_context_fragments_count
        if max_question_length is not None:
            config_kwargs['max_question_length'] = max_question_length
        if max_history_messages_count is not None:
            config_kwargs['max_history_messages_count'] = max_history_messages_count
        if custom_system_prompt is not None:
            config_kwargs['custom_system_prompt'] = custom_system_prompt

        configuration = DocumentQuestionConfiguration(**config_kwargs)

        return cls(
            ollama_llm_facade=ollama_llm_facade,
            document_context_provider=document_context_provider,
            configuration=configuration
        )

    async def execute_document_question(self,
                                        request: DocumentQuestionRequest) -> DocumentQuestionResponse:
        logger.info(
            "Starting document question execution",
            extra={
                "question": request.question,
                "history_messages": request.history_messages if request.history_messages else None
            }
        )

        self._request_validator.validate_request(request)

        context_fragments = await self.retrieve_context_fragments_by_question(request.question)

        answer = await self.generate_answer(
            question=request.question,
            history_messages=request.history_messages or [],
            context_fragments=context_fragments
        )

        logger.info(
            "Document question executed successfully",
            extra={
                "question": request.question,
                "answer": answer
            }
        )

        return DocumentQuestionResponse(
            answer=answer
        )

    async def retrieve_context_fragments_by_question(self,
                                                     question: str,
                                                     max_context_fragments_count: Optional[int] = None) -> List[str]:
        max_context_fragments_count = max_context_fragments_count or self._configuration.max_context_fragments_count

        logger.debug(
            "Retrieving context fragments",
            extra={
                "question": question,
                "max_context_fragments_count": max_context_fragments_count
            }
        )

        try:
            fragments = await self._document_context_provider.retrieve_context_fragments_by_question(
                question=question,
                max_context_fragments_count=max_context_fragments_count
            )

            logger.info(
                "Context fragments retrieved successfully",
                extra={
                    "fragments": fragments,
                }
            )

            return fragments

        except Exception as e:
            logger.exception(
                "Unexpected error during context retrieval",
                extra={
                    "error_type": type(e).__name__,
                    "question": question,
                    "max_context_fragments_count": max_context_fragments_count
                }
            )
            raise DocumentQuestionServiceError("Error inesperado al recuperar fragmentos del documento") from e

    async def generate_answer(self,
                              question: str,
                              history_messages: Optional[List[Message]] = None,
                              context_fragments: Optional[List[str]] = None) -> str:
        logger.debug(
            "Generating answer",
            extra={
                "question": question,
                "history_messages": history_messages,
                "context_fragments": context_fragments
            }
        )

        try:
            await self._ensure_llm_initialized()

            prompt = self._build_prompt(
                question=question,
                context_fragments=context_fragments,
                history_messages=history_messages
            )

            answer = await self._invoke_llm(prompt)

            if not answer or not answer.strip():
                logger.warning("LLM returned empty answer")
                raise DocumentQuestionServiceError("El modelo no generó una respuesta válida")

            logger.info(
                "Answer generated successfully",
                extra={
                    "answer": answer
                }
            )

            return answer.strip()

        except Exception as e:
            logger.exception(
                "Unexpected error during answer generation",
                extra={
                    "error_type": type(e).__name__
                }
            )
            raise DocumentQuestionServiceError("Error inesperado al generar la respuesta") from e

    async def _ensure_llm_initialized(self) -> None:
        if self._llm is not None:
            return

        if self._llm_initialization_failed:
            raise DocumentQuestionServiceError("El modelo de lenguaje no pudo ser inicializado previamente")

        logger.debug("Initializing LLM")

        try:
            self._llm = await self._ollama_llm_facade.get_llm_base()
            logger.info("LLM initialized successfully")
        except Exception as e:
            self._llm_initialization_failed = True
            logger.error(
                "LLM initialization failed",
                extra={
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise DocumentQuestionServiceError("Error al inicializar el modelo de lenguaje") from e

    def _build_prompt(self,
                      question: str,
                      context_fragments: Optional[List[str]] = None,
                      history_messages: Optional[List[Message]] = None) -> List[BaseMessage]:
        return self._prompt_builder.build_complete_prompt(
            system_prompt=self._configuration.system_prompt,
            question=question,
            context_fragments=context_fragments,
            history_messages=history_messages
        )

    async def _invoke_llm(self,
                          prompt: List[BaseMessage]) -> str:
        if self._llm is None:
            raise DocumentQuestionServiceError("LLM no inicializado. Esto no debería ocurrir.")

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
                    "answer": answer
                }
            )

            return answer

        except Exception as e:
            logger.exception(
                "Unexpected error during LLM invocation",
                extra={
                    "error_type": type(e).__name__
                }
            )
            raise DocumentQuestionServiceError("Error inesperado al invocar el modelo de lenguaje") from e
