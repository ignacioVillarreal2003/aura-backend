import logging
from collections.abc import AsyncIterator
from typing import Optional

from fastapi import HTTPException, Request, status

from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.user_interactions.document_action_service.constants.processing_strategy import ProcessingStrategy
from app.application.services.user_interactions.document_action_service.document_action_settings import DocumentActionServiceSettings
from app.application.services.user_interactions.document_action_service.document_action_state import DocumentActionState
from app.application.services.user_interactions.document_action_service.exceptions.document_action_service_exceptions import (
    DocumentActionServiceException,
)
from app.application.services.user_interactions.document_action_service.interfaces.document_action_service_interface import (
    DocumentActionServiceInterface,
)
from app.application.services.user_interactions.document_action_service.processors.chunk_document_action_processor.chunk_document_action_processor import \
    ChunkDocumentActionProcessor
from app.application.services.user_interactions.document_action_service.processors.context_document_action_processor.context_document_action_processor import (
    ContextDocumentActionProcessor,
)
from app.application.services.user_interactions.document_action_service.processors.direct_document_action_processor.direct_document_action_processor import (
    DirectDocumentActionProcessor,
)
from app.application.services.user_interactions.document_action_service.processors.reduce_document_action_processor.reduce_document_action_processor import (
    ReduceDocumentActionProcessor,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document_action_type import DocumentActionType
from app.domain.dtos.user_interactions.document_action.document_action_request import DocumentActionRequest
from app.domain.dtos.user_interactions.document_action.document_action_response import DocumentActionResponse
from app.domain.dtos.user_interactions.document_action.document_action_stream_events import (
    DocumentActionStreamComplete,
    DocumentActionStreamError,
    DocumentActionStreamEvent,
    DocumentActionStreamProgress,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_streaming_invoker_interface import (
    OllamaLLMStreamingInvokerInterface,
)

logger = logging.getLogger(__name__)

_ACTION_DIRECT_MESSAGES: dict[DocumentActionType, str] = {
    DocumentActionType.summarize: "Generando el resumen del documento...",
    DocumentActionType.essay: "Redactando el ensayo...",
    DocumentActionType.key_points: "Extrayendo los puntos clave del documento...",
    DocumentActionType.compare: "Comparando los documentos...",
    DocumentActionType.analyze: "Analizando el contenido del documento...",
    DocumentActionType.explain: "Elaborando la explicación del contenido...",
    DocumentActionType.report: "Redactando el reporte del documento...",
}

_STATIC_FALLBACK_MESSAGE = (
    "No se encontró información suficiente en los documentos para generar una respuesta. "
    "Verifique que los documentos estén correctamente cargados en el sistema o contacte al administrador."
)

_KNOWN_EXCEPTIONS = (
    RequestValidationException,
    DocumentActionServiceException,
    UnauthorizedException,
)


class DocumentActionService(DocumentActionServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            ollama_llm_streaming_invoker: OllamaLLMStreamingInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            document_action_settings: Optional[DocumentActionServiceSettings] = None,
    ) -> None:
        self._document_action_settings = document_action_settings or DocumentActionServiceSettings()

        self._context_processor = ContextDocumentActionProcessor(
            document_action_service_settings=self._document_action_settings,
            document_context_provider=document_context_provider,
        )
        self._direct_processor = DirectDocumentActionProcessor(
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
            ollama_llm_streaming_invoker=ollama_llm_streaming_invoker,
        )
        self._chunk_processor = ChunkDocumentActionProcessor(
            document_action_service_settings=self._document_action_settings,
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
        )
        self._reduce_processor = ReduceDocumentActionProcessor(
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
            ollama_llm_streaming_invoker=ollama_llm_streaming_invoker,
        )

    async def execute_document_action(
            self,
            document_action_request: DocumentActionRequest,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentActionResponse:
        logger.info(
            "Document action execution initiated",
            extra={
                "user_id": authenticated_user.id,
                "document_ids": document_action_request.document_ids,
                "action": document_action_request.action.value if document_action_request.action else None,
            },
        )
        try:
            state = DocumentActionState.from_request(document_action_request, authenticated_user)
            await self._run_pipeline(state)
            logger.info(
                "Document action execution completed",
                extra={"user_id": authenticated_user.id, "document_ids": document_action_request.document_ids},
            )
            return DocumentActionResponse(
                result=state.result,
                document_ids=state.document_ids,
                instruction=state.instruction,
                action=state.action,
                fragments=state.all_fragments,
            )
        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during document action execution",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise DocumentActionServiceException(
                "Unexpected error while processing the document action"
            ) from e

    async def execute_document_action_stream(
            self,
            document_action_request: DocumentActionRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[DocumentActionStreamEvent]:
        try:
            state = DocumentActionState.from_request(document_action_request, authenticated_user)

            yield DocumentActionStreamProgress(
                step="context_retrieval",
                message="Leyendo el contenido del documento...",
            )
            await self._context_processor.run(state)

            if state.strategy == ProcessingStrategy.direct:
                action_message = _ACTION_DIRECT_MESSAGES.get(
                    document_action_request.action,
                    "Ejecutando la instrucción sobre el documento...",
                )
                yield DocumentActionStreamProgress(
                    step="action_execution",
                    message=action_message,
                )
                try:
                    async for delta in self._direct_processor.stream(state):
                        yield delta
                except DocumentActionServiceException as e:
                    yield DocumentActionStreamError(message=e.message, code=e.code)
                    return
                except Exception as e:
                    logger.exception(
                        "Error during direct action streaming",
                        extra={"error_type": type(e).__name__},
                    )
                    yield DocumentActionStreamError(
                        message="Error invoking the language model",
                        code="StreamActionError",
                    )
                    return

            elif state.strategy == ProcessingStrategy.map_reduce:
                yield DocumentActionStreamProgress(
                    step="chunk_processing",
                    message="Procesando el documento por secciones...",
                )
                await self._chunk_processor.run(state)

                yield DocumentActionStreamProgress(
                    step="reducing",
                    message="Integrando los resultados en la respuesta final...",
                )
                try:
                    async for delta in self._reduce_processor.stream(state):
                        yield delta
                except DocumentActionServiceException as e:
                    yield DocumentActionStreamError(message=e.message, code=e.code)
                    return
                except Exception as e:
                    logger.exception(
                        "Error during reduce action streaming",
                        extra={"error_type": type(e).__name__},
                    )
                    yield DocumentActionStreamError(
                        message="Error invoking the language model",
                        code="StreamActionError",
                    )
                    return

            state.result = state.result.strip()
            if not state.result:
                state.result = _STATIC_FALLBACK_MESSAGE

            yield DocumentActionStreamComplete(
                result=DocumentActionResponse(
                    result=state.result,
                    document_ids=state.document_ids,
                    instruction=state.instruction,
                    action=state.action,
                    fragments=state.all_fragments,
                ),
            )

        except _KNOWN_EXCEPTIONS as e:
            logger.warning(
                "Known error during document action stream",
                extra={"error_type": type(e).__name__},
            )
            yield DocumentActionStreamError(message=str(e), code=type(e).__name__)
        except Exception as e:
            logger.exception(
                "Unexpected error during document action stream",
                extra={"error_type": type(e).__name__},
            )
            yield DocumentActionStreamError(
                message="Unexpected error while processing the document action",
                code="DocumentActionStreamError",
            )

    async def _run_pipeline(self, state: DocumentActionState) -> None:
        await self._context_processor.run(state)
        await self._direct_processor.run(state)
        await self._chunk_processor.run(state)
        await self._reduce_processor.run(state)
        if not state.result.strip():
            state.result = _STATIC_FALLBACK_MESSAGE


async def get_document_action_service(request: Request) -> DocumentActionServiceInterface:
    try:
        return request.app.state.document_action_service
    except AttributeError:
        logger.error("DocumentActionService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocumentActionService is not available",
        )
