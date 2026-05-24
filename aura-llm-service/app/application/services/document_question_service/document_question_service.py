import logging
from collections.abc import AsyncIterator
from typing import Optional
from fastapi import HTTPException, Request, status

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.authorization.permissions import Permissions
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings,
)
from app.application.services.document_question_service.document_question_state import DocumentQuestionState
from app.application.services.document_question_service.exceptions.document_question_service_exceptions import (
    DocumentQuestionServiceException,
)
from app.application.services.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface,
)
from app.application.services.document_question_service.processors.answer_document_question_processor.answer_document_question_processor import (
    AnswerDocumentQuestionProcessor,
)
from app.application.services.document_question_service.processors.context_document_question_processor.context_document_question_processor import (
    ContextDocumentQuestionProcessor,
)
from app.application.services.document_question_service.processors.question_document_question_processor.question_document_question_processor import (
    QuestionDocumentQuestionProcessor,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question.document_question_response import DocumentQuestionResponse
from app.domain.dtos.document_question.document_question_stream_events import (
    DocumentQuestionStreamComplete,
    DocumentQuestionStreamError,
    DocumentQuestionStreamEvent,
    DocumentQuestionStreamMeta,
    DocumentQuestionStreamProgress,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_invoker_exceptions import LLMInvocationError
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_streaming_invoker_interface import (
    OllamaLLMStreamingInvokerInterface,
)

logger = logging.getLogger(__name__)

_STATIC_FALLBACK_MESSAGE = (
    "No se encontró información relevante en la base documental para responder su consulta. "
    "Por favor, reformule su pregunta o consulte directamente la documentación disponible."
)


class DocumentQuestionService(DocumentQuestionServiceInterface):
    _KNOWN_EXCEPTIONS = (
        RequestValidationException,
        DocumentQuestionServiceException,
        UnauthorizedException,
    )

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            ollama_llm_streaming_invoker: OllamaLLMStreamingInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            authorizer: Authorizer,
            document_question_service_settings: Optional[DocumentQuestionServiceSettings] = None,
    ) -> None:
        self._authorizer = authorizer
        self._settings = document_question_service_settings or DocumentQuestionServiceSettings()

        self._question_processor = QuestionDocumentQuestionProcessor(
            document_question_service_settings=self._settings,
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
        )
        self._context_processor = ContextDocumentQuestionProcessor(
            document_question_service_settings=self._settings,
            document_context_provider=document_context_provider,
        )
        self._answer_processor = AnswerDocumentQuestionProcessor(
            document_question_service_settings=self._settings,
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
            ollama_llm_streaming_invoker=ollama_llm_streaming_invoker,
        )

    async def execute_document_question(
            self,
            document_question_request: DocumentQuestionRequest,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentQuestionResponse:
        logger.info("Document question execution initiated")
        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_DOCUMENT_QUESTION}),
        )
        try:
            state = DocumentQuestionState.from_request(document_question_request, authenticated_user)
            await self._run_pipeline(state)
            logger.info("Document question execution completed")
            return DocumentQuestionResponse(
                question=state.current_message.content,
                answer=state.answer,
                messages=state.messages,
                fragments=state.fragments,
            )
        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during document question execution",
                extra={"error_type": type(e).__name__},
            )
            raise DocumentQuestionServiceException(
                "Unexpected error while processing the question"
            ) from e

    async def execute_document_question_stream(
            self,
            document_question_request: DocumentQuestionRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[DocumentQuestionStreamEvent]:
        try:
            state = DocumentQuestionState.from_request(document_question_request, authenticated_user)

            if self._settings.question_processor_enabled:
                yield DocumentQuestionStreamProgress(
                    step="question_processing",
                    message="Analizando y reformulando la consulta...",
                )
            await self._question_processor.run(state)

            yield DocumentQuestionStreamProgress(
                step="context_retrieval",
                message="Recuperando fragmentos de contexto relevantes...",
            )
            await self._context_processor.run(state)

            yield DocumentQuestionStreamMeta(
                question=state.current_message.content,
                fragments=list(state.fragments),
            )

            if state.fragments:
                yield DocumentQuestionStreamProgress(
                    step="answer_generation",
                    message="Generando respuesta con el contexto encontrado...",
                )
                try:
                    async for delta in self._answer_processor.stream(state):
                        yield delta
                except LLMInvocationError as e:
                    logger.exception("LLM error during answer streaming")
                    yield DocumentQuestionStreamError(message=str(e), code=type(e).__name__)
                    return
                except Exception as e:
                    logger.exception(
                        "Error during answer streaming",
                        extra={"error_type": type(e).__name__},
                    )
                    yield DocumentQuestionStreamError(
                        message="Error invoking the language model",
                        code="StreamAnswerError",
                    )
                    return

            state.answer = state.answer.strip()
            if not state.answer:
                state.answer = _STATIC_FALLBACK_MESSAGE

            yield DocumentQuestionStreamComplete(
                result=DocumentQuestionResponse(
                    question=state.current_message.content,
                    answer=state.answer,
                    messages=state.messages,
                    fragments=state.fragments,
                ),
            )

        except RequestValidationException as e:
            yield DocumentQuestionStreamError(message=e.message, code=e.code)
        except DocumentQuestionServiceException as e:
            yield DocumentQuestionStreamError(message=e.message, code=e.code)
        except Exception as e:
            logger.exception(
                "Unexpected error during document question stream",
                extra={"error_type": type(e).__name__},
            )
            yield DocumentQuestionStreamError(
                message="Unexpected error while processing the question",
                code="DocumentQuestionStreamError",
            )

    async def _run_pipeline(self, state: DocumentQuestionState) -> None:
        await self._question_processor.run(state)
        await self._context_processor.run(state)
        await self._answer_processor.run(state)
        if not state.answer.strip():
            state.answer = _STATIC_FALLBACK_MESSAGE


async def get_document_question_service(request: Request) -> DocumentQuestionServiceInterface:
    try:
        return request.app.state.document_question_service
    except AttributeError:
        logger.error("DocumentQuestionService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocumentQuestionService is not available",
        )
