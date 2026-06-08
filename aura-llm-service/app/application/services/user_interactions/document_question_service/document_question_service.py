import logging
from collections.abc import AsyncIterator
from typing import Optional
from fastapi import HTTPException, Request, status

from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.user_interactions.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings,
)
from app.domain.field_limits import MAX_CONTENT_CHARS
from app.application.services.user_interactions.document_question_service.document_question_state import DocumentQuestionState
from app.application.services.user_interactions.document_question_service.exceptions.document_question_service_exceptions import (
    DocumentQuestionServiceException,
)
from app.application.services.user_interactions.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface,
)
from app.application.services.user_interactions.document_question_service.processors.answer_document_question_processor.answer_document_question_processor import (
    AnswerDocumentQuestionProcessor,
)
from app.application.services.user_interactions.document_question_service.processors.attached_reduction_processor.attached_reduction_processor import (
    AttachedReductionProcessor,
)
from app.application.services.user_interactions.document_question_service.processors.context_document_question_processor.context_document_question_processor import (
    ContextDocumentQuestionProcessor,
)
from app.application.services.user_interactions.document_question_service.processors.question_document_question_processor.question_document_question_processor import (
    QuestionDocumentQuestionProcessor,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.user_interactions.document_question.document_question_response import DocumentQuestionResponse
from app.domain.dtos.user_interactions.document_question.document_question_stream_events import (
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

_KNOWN_EXCEPTIONS = (
    RequestValidationException,
    DocumentQuestionServiceException,
    UnauthorizedException,
)


class DocumentQuestionService(DocumentQuestionServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            ollama_llm_streaming_invoker: OllamaLLMStreamingInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            document_question_settings: Optional[DocumentQuestionServiceSettings] = None,
    ) -> None:
        self._document_question_settings = document_question_settings or DocumentQuestionServiceSettings()
        self._document_context_provider = document_context_provider

        self._question_processor = QuestionDocumentQuestionProcessor(
            document_question_service_settings=self._document_question_settings,
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
        )
        self._context_processor = ContextDocumentQuestionProcessor(
            document_question_service_settings=self._document_question_settings,
            document_context_provider=document_context_provider,
        )
        self._attached_reduction_processor = AttachedReductionProcessor(
            settings=self._document_question_settings,
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
        )
        self._answer_processor = AnswerDocumentQuestionProcessor(
            document_question_service_settings=self._document_question_settings,
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
            ollama_llm_streaming_invoker=ollama_llm_streaming_invoker,
        )

    async def execute_document_question(
            self,
            document_question_request: DocumentQuestionRequest,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentQuestionResponse:
        logger.info(
            "Document question execution initiated",
            extra={"user_id": authenticated_user.id},
        )
        try:
            state = DocumentQuestionState.from_request(document_question_request, authenticated_user)
            await self._run_pipeline(state)
            logger.info(
                "Document question execution completed",
                extra={"user_id": authenticated_user.id},
            )
            return DocumentQuestionResponse(
                question=state.current_message.content,
                answer=state.answer,
                messages=state.messages,
                fragments=state.all_fragments,
            )
        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during document question execution",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
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

            if state.document_ids:
                yield DocumentQuestionStreamProgress(
                    step="loading_documents",
                    message="Leyendo documentos adjuntos...",
                )
            await self._fetch_attached_fragments(state)

            if self._document_question_settings.question_processor_enabled:
                yield DocumentQuestionStreamProgress(
                    step="question_processing",
                    message="Interpretando y optimizando la pregunta...",
                )
            await self._question_processor.run(state)

            if self._attached_reduction_processor.is_needed(state):
                yield DocumentQuestionStreamProgress(
                    step="document_reduction",
                    message="Analizando el contenido del documento...",
                )
            await self._attached_reduction_processor.run(state)

            yield DocumentQuestionStreamProgress(
                step="context_retrieval",
                message="Buscando información relevante en los documentos...",
            )
            await self._context_processor.run(state)

            yield DocumentQuestionStreamMeta(
                question=state.current_message.content,
                fragments=list(state.all_fragments),
            )

            if state.all_fragments or state.reduced_attached_context:
                yield DocumentQuestionStreamProgress(
                    step="answer_generation",
                    message="Elaborando la respuesta con base en la documentación...",
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
            if len(state.answer) > MAX_CONTENT_CHARS:
                state.answer = state.answer[:MAX_CONTENT_CHARS]

            yield DocumentQuestionStreamComplete(
                result=DocumentQuestionResponse(
                    question=state.current_message.content,
                    answer=state.answer,
                    messages=state.messages,
                    fragments=state.all_fragments,
                ),
            )

        except _KNOWN_EXCEPTIONS as e:
            logger.warning(
                "Known error during document question stream",
                extra={"error_type": type(e).__name__},
            )
            yield DocumentQuestionStreamError(message=str(e), code=type(e).__name__)
        except Exception as e:
            logger.exception(
                "Unexpected error during document question stream",
                extra={"error_type": type(e).__name__},
            )
            yield DocumentQuestionStreamError(
                message="Unexpected error while processing the question",
                code="DocumentQuestionStreamError",
            )

    async def _fetch_attached_fragments(self, state: DocumentQuestionState) -> None:
        if not state.document_ids:
            return
        try:
            result = await self._document_context_provider.retrieve_context_fragments_by_document(
                authenticated_user=state.authenticated_user,
                document_ids=state.document_ids,
            )
            state.attached_fragments = result.fragments[:self._document_question_settings.max_attached_fragments]
            logger.debug(
                "Attached document fragments retrieved for document question",
                extra={
                    "fragment_count": len(state.attached_fragments),
                    "document_count": len(state.document_ids),
                },
            )
        except Exception:
            logger.warning(
                "Attached document retrieval failed; continuing without attachments",
                extra={"user_id": state.authenticated_user.id},
                exc_info=True,
            )
            state.attached_fragments = []

    async def _run_pipeline(self, state: DocumentQuestionState) -> None:
        await self._fetch_attached_fragments(state)
        await self._question_processor.run(state)
        await self._attached_reduction_processor.run(state)
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
