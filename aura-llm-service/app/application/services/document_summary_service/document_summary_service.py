import logging
from collections.abc import AsyncIterator
from typing import Optional
from fastapi import HTTPException, Request, status

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.authorization.permissions import Permissions
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.document_summary_service.constants.summarization_strategy import SummarizationStrategy
from app.application.services.document_summary_service.document_summary_settings import DocumentSummaryServiceSettings
from app.application.services.document_summary_service.document_summary_state import DocumentSummaryState
from app.application.services.document_summary_service.exceptions.document_summary_service_exceptions import (
    DocumentSummaryServiceException,
)
from app.application.services.document_summary_service.interfaces.document_summary_service_interface import (
    DocumentSummaryServiceInterface,
)
from app.application.services.document_summary_service.processors.context_document_summary_processor.context_document_summary_processor import (
    ContextDocumentSummaryProcessor,
)
from app.application.services.document_summary_service.processors.direct_document_summary_processor.direct_document_summary_processor import (
    DirectDocumentSummaryProcessor,
)
from app.application.services.document_summary_service.processors.chunk_document_summary_processor.chunk_document_summary_processor import (
    ChunkDocumentSummaryProcessor,
)
from app.application.services.document_summary_service.processors.reduce_document_summary_processor.reduce_document_summary_processor import (
    ReduceDocumentSummaryProcessor,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document_summary.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.document_summary.document_summary_response import DocumentSummaryResponse
from app.domain.dtos.document_summary.document_summary_stream_events import (
    DocumentSummaryStreamComplete,
    DocumentSummaryStreamError,
    DocumentSummaryStreamEvent,
    DocumentSummaryStreamProgress,
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

_STATIC_FALLBACK_MESSAGE = (
    "No se encontró información suficiente en el documento para generar un resumen. "
    "Verifique que el documento esté correctamente cargado en el sistema o contacte al administrador."
)

_KNOWN_EXCEPTIONS = (
    RequestValidationException,
    DocumentSummaryServiceException,
    UnauthorizedException,
)


class DocumentSummaryService(DocumentSummaryServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            ollama_llm_streaming_invoker: OllamaLLMStreamingInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            authorizer: Authorizer,
            document_summary_service_settings: Optional[DocumentSummaryServiceSettings] = None,
    ) -> None:
        self._authorizer = authorizer
        self._settings = document_summary_service_settings or DocumentSummaryServiceSettings()

        self._context_processor = ContextDocumentSummaryProcessor(
            document_summary_service_settings=self._settings,
            document_context_provider=document_context_provider,
        )
        self._direct_processor = DirectDocumentSummaryProcessor(
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
            ollama_llm_streaming_invoker=ollama_llm_streaming_invoker,
        )
        self._map_chunks_processor = ChunkDocumentSummaryProcessor(
            document_summary_service_settings=self._settings,
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
        )
        self._reduce_processor = ReduceDocumentSummaryProcessor(
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
            ollama_llm_streaming_invoker=ollama_llm_streaming_invoker,
        )

    async def execute_document_summary(
            self,
            document_summary_request: DocumentSummaryRequest,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentSummaryResponse:
        logger.info(
            "Document summary execution initiated",
            extra={"user_id": authenticated_user.id, "document_ids": document_summary_request.document_ids},
        )
        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_DOCUMENT_SUMMARY}),
        )
        try:
            state = DocumentSummaryState.from_request(document_summary_request, authenticated_user)
            await self._run_pipeline(state)
            logger.info(
                "Document summary execution completed",
                extra={"user_id": authenticated_user.id, "document_ids": document_summary_request.document_ids},
            )
            return DocumentSummaryResponse(
                document_ids=state.document_ids,
                summary=state.summary,
                fragments=state.fragments,
            )
        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during document summary execution",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise DocumentSummaryServiceException(
                "Unexpected error while processing the document summary"
            ) from e

    async def execute_document_summary_stream(
            self,
            document_summary_request: DocumentSummaryRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[DocumentSummaryStreamEvent]:
        try:
            state = DocumentSummaryState.from_request(document_summary_request, authenticated_user)

            yield DocumentSummaryStreamProgress(
                step="context_retrieval",
                message="Recuperando fragmentos de contexto...",
            )
            await self._context_processor.run(state)

            if state.strategy == SummarizationStrategy.direct:
                yield DocumentSummaryStreamProgress(
                    step="summarization",
                    message="Generando resumen del documento...",
                )
                try:
                    async for delta in self._direct_processor.stream(state):
                        yield delta
                except DocumentSummaryServiceException as e:
                    yield DocumentSummaryStreamError(message=e.message, code=e.code)
                    return
                except Exception as e:
                    logger.exception(
                        "Error during direct summary streaming",
                        extra={"error_type": type(e).__name__},
                    )
                    yield DocumentSummaryStreamError(
                        message="Error invoking the language model",
                        code="StreamSummaryError",
                    )
                    return

            elif state.strategy == SummarizationStrategy.map_reduce:
                yield DocumentSummaryStreamProgress(
                    step="chunk_processing",
                    message="Procesando fragmentos del documento en paralelo...",
                )
                await self._map_chunks_processor.run(state)

                yield DocumentSummaryStreamProgress(
                    step="reducing",
                    message="Generando resumen final a partir de los fragmentos procesados...",
                )
                try:
                    async for delta in self._reduce_processor.stream(state):
                        yield delta
                except DocumentSummaryServiceException as e:
                    yield DocumentSummaryStreamError(message=e.message, code=e.code)
                    return
                except Exception as e:
                    logger.exception(
                        "Error during reduce summary streaming",
                        extra={"error_type": type(e).__name__},
                    )
                    yield DocumentSummaryStreamError(
                        message="Error invoking the language model",
                        code="StreamSummaryError",
                    )
                    return

            state.summary = state.summary.strip()
            if not state.summary:
                state.summary = _STATIC_FALLBACK_MESSAGE

            yield DocumentSummaryStreamComplete(
                result=DocumentSummaryResponse(
                    document_ids=state.document_ids,
                    summary=state.summary,
                    fragments=state.fragments,
                ),
            )

        except RequestValidationException as e:
            yield DocumentSummaryStreamError(message=e.message, code=e.code)
        except DocumentSummaryServiceException as e:
            yield DocumentSummaryStreamError(message=e.message, code=e.code)
        except Exception as e:
            logger.exception(
                "Unexpected error during document summary stream",
                extra={"error_type": type(e).__name__},
            )
            yield DocumentSummaryStreamError(
                message="Unexpected error while processing the document summary",
                code="DocumentSummaryStreamError",
            )

    async def _run_pipeline(self, state: DocumentSummaryState) -> None:
        await self._context_processor.run(state)
        await self._direct_processor.run(state)
        await self._map_chunks_processor.run(state)
        await self._reduce_processor.run(state)
        if not state.summary.strip():
            state.summary = _STATIC_FALLBACK_MESSAGE


async def get_document_summary_service(request: Request) -> DocumentSummaryServiceInterface:
    try:
        return request.app.state.document_summary_service
    except AttributeError:
        logger.error("DocumentSummaryService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocumentSummaryService is not available",
        )
