import logging
from typing import Optional

from fastapi import HTTPException, Request, status

from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.document_action_service.document_action_settings import (
    DocumentActionServiceSettings,
)
from app.application.services.document_action_service.exceptions.document_action_service_exceptions import (
    DocumentActionServiceException,
)
from app.application.services.document_action_service.interfaces.document_action_plugin_interface import (
    DocumentActionPlugin,
)
from app.application.services.document_action_service.interfaces.document_action_service_interface import (
    DocumentActionServiceInterface,
)
from app.application.services.document_action_service.pipeline.document_action_pipeline import (
    DocumentActionPipeline,
)
from app.application.services.document_action_service.pipeline.document_action_pipeline_resources import (
    DocumentActionPipelineResources,
)
from app.application.services.document_action_service.pipeline.document_action_pipeline_state import (
    DocumentActionPipelineState,
)
from app.application.services.document_action_service.steps.fallback_response.fallback_response_plugin import (
    FallbackResponsePlugin,
)
from app.application.services.document_action_service.steps.generate_response_direct.generate_response_direct_plugin import (
    GenerateResponseDirectPlugin,
)
from app.application.services.document_action_service.steps.map_chunks.map_chunks_plugin import MapChunksPlugin
from app.application.services.document_action_service.steps.reduce_results.reduce_results_plugin import (
    ReduceResultsPlugin,
)
from app.application.services.document_action_service.steps.retrieve_fragments.retrieve_fragments_plugin import (
    RetrieveFragmentsPlugin,
)
from app.application.services.document_action_service.steps.validate_request.validate_request_plugin import (
    ValidateRequestPlugin,
)
from app.domain.dtos.document_action.document_action_request import DocumentActionRequest
from app.domain.dtos.document_action.document_action_response import DocumentActionResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


class DocumentActionService(DocumentActionServiceInterface):
    _KNOWN_EXCEPTIONS = (
        RequestValidationException,
        DocumentActionServiceException,
    )

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            document_action_service_settings: Optional[DocumentActionServiceSettings] = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._llm_invoker = llm_invoker
        self._document_context_provider = document_context_provider
        settings = document_action_service_settings or DocumentActionServiceSettings()
        self._pipeline = DocumentActionPipeline(
            plugins=self._build_pipeline_plugins(settings.pipeline_plugins),
        )
        logger.info("DocumentActionService initialized successfully")

    async def execute_document_action(
            self,
            document_action_request: DocumentActionRequest,
            authenticated_user: AuthenticationResponse,
            authorization_token: Optional[str] = None,
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
            state = DocumentActionPipelineState.from_request(
                document_action_request,
                authorization_token=authorization_token,
                authenticated_user=authenticated_user,
            )
            resources = DocumentActionPipelineResources(
                ollama_llm_facade=self._ollama_llm_facade,
                llm_invoker=self._llm_invoker,
                document_context_provider=self._document_context_provider,
            )

            await self._pipeline.run(state=state, resources=resources)

            logger.info(
                "Document action execution completed",
                extra={
                    "user_id": authenticated_user.id,
                    "document_ids": document_action_request.document_ids,
                },
            )
            return DocumentActionResponse(
                result=state.result,
                document_ids=state.document_ids,
                action=state.action,
            )

        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during document action execution",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise DocumentActionServiceException(
                "Unexpected error while processing the document action"
            ) from e

    @staticmethod
    def _build_pipeline_plugins(plugin_names: list[str]) -> list[DocumentActionPlugin]:
        registry: dict[str, type[DocumentActionPlugin]] = {
            "validate_request": ValidateRequestPlugin,
            "retrieve_fragments": RetrieveFragmentsPlugin,
            "generate_response_direct": GenerateResponseDirectPlugin,
            "map_chunks": MapChunksPlugin,
            "reduce_results": ReduceResultsPlugin,
            "fallback_response": FallbackResponsePlugin,
        }

        plugins: list[DocumentActionPlugin] = []
        for name in plugin_names:
            plugin_cls = registry.get(name)
            if plugin_cls is None:
                logger.warning(
                    "Unknown document_action pipeline plugin",
                    extra={"plugin_name": name},
                )
                continue
            plugins.append(plugin_cls())

        return plugins


async def get_document_action_service(request: Request) -> DocumentActionServiceInterface:
    try:
        return request.app.state.document_action_service
    except AttributeError:
        logger.error("DocumentActionService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocumentActionService is not available",
        )
