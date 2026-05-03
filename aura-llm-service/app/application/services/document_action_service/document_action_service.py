import logging
from typing import Optional

from fastapi import HTTPException, Request, status

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.authorization.permissions import Permissions
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.document_action_service.document_action_settings import DocumentActionServiceSettings
from app.application.services.document_action_service.document_action_state import DocumentActionState
from app.application.services.document_action_service.exceptions.document_action_service_exceptions import (
    DocumentActionServiceException,
)
from app.application.services.document_action_service.interfaces.document_action_service_interface import (
    DocumentActionServiceInterface,
)
from app.application.services.document_action_service.processors.chunk_document_action_processor.chunk_document_action_processor import \
    ChunkDocumentActionProcessor
from app.application.services.document_action_service.processors.context_document_action_processor.context_document_action_processor import (
    ContextDocumentActionProcessor,
)
from app.application.services.document_action_service.processors.direct_document_action_processor.direct_document_action_processor import (
    DirectDocumentActionProcessor,
)
from app.application.services.document_action_service.processors.fallback_document_action_processor.fallback_document_action_processor import (
    FallbackDocumentActionProcessor,
)
from app.application.services.document_action_service.processors.reduce_document_action_processor.reduce_document_action_processor import (
    ReduceDocumentActionProcessor,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document_action.document_action_request import DocumentActionRequest
from app.domain.dtos.document_action.document_action_response import DocumentActionResponse
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

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
            document_context_provider: DocumentContextProviderInterface,
            authorizer: Authorizer,
            document_action_service_settings: Optional[DocumentActionServiceSettings] = None,
    ) -> None:
        self._authorizer = authorizer
        self._settings = document_action_service_settings or DocumentActionServiceSettings()

        self._context_processor = ContextDocumentActionProcessor(
            document_action_service_settings=self._settings,
            document_context_provider=document_context_provider,
        )
        self._direct_processor = DirectDocumentActionProcessor(
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
        )
        self._chunk_processor = ChunkDocumentActionProcessor(
            document_action_service_settings=self._settings,
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
        )
        self._reduce_processor = ReduceDocumentActionProcessor(
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
        )
        self._fallback_processor = FallbackDocumentActionProcessor(
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
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
        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_DOCUMENT_ACTION}),
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
                action=state.action,
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

    async def _run_pipeline(self, state: DocumentActionState) -> None:
        await self._context_processor.run(state)
        await self._direct_processor.run(state)
        await self._chunk_processor.run(state)
        await self._reduce_processor.run(state)
        await self._fallback_processor.run(state)


async def get_document_action_service(request: Request) -> DocumentActionServiceInterface:
    try:
        return request.app.state.document_action_service
    except AttributeError:
        logger.error("DocumentActionService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocumentActionService is not available",
        )
