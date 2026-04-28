import logging
from typing import Optional
from fastapi import HTTPException, Request, status

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.authorization.permissions import Permissions
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.document_summary_service.document_summary_settings import (
    DocumentSummaryServiceSettings,
)
from app.application.services.document_summary_service.exceptions.document_summary_service_exceptions import (
    DocumentSummaryServiceException,
)
from app.application.services.document_summary_service.interfaces.document_summary_plugin_interface import (
    DocumentSummaryPlugin,
)
from app.application.services.document_summary_service.interfaces.document_summary_service_interface import (
    DocumentSummaryServiceInterface,
)
from app.application.services.document_summary_service.pipeline.document_summary_pipeline import (
    DocumentSummaryPipeline,
)
from app.application.services.document_summary_service.pipeline.document_summary_pipeline_resources import (
    DocumentSummaryPipelineResources,
)
from app.application.services.document_summary_service.pipeline.document_summary_pipeline_state import (
    DocumentSummaryPipelineState,
)
from app.application.services.document_summary_service.steps.fallback_summary.fallback_summary_plugin import (
    FallbackSummaryPlugin,
)
from app.application.services.document_summary_service.steps.generate_summary_direct.generate_summary_direct_plugin import (
    GenerateSummaryDirectPlugin,
)
from app.application.services.document_summary_service.steps.map_chunks.map_chunks_plugin import MapChunksPlugin
from app.application.services.document_summary_service.steps.reduce_summaries.reduce_summaries_plugin import (
    ReduceSummariesPlugin,
)
from app.application.services.document_summary_service.steps.retrieve_fragments.retrieve_fragments_plugin import (
    RetrieveFragmentsPlugin,
)
from app.application.services.document_summary_service.steps.validate_request.validate_request_plugin import (
    ValidateRequestPlugin,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document_summary.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.document_summary.document_summary_response import DocumentSummaryResponse
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


class DocumentSummaryService(DocumentSummaryServiceInterface):
    _KNOWN_EXCEPTIONS = (
        RequestValidationException,
        DocumentSummaryServiceException,
        UnauthorizedException,
    )

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            authorizer: Authorizer,
            document_summary_service_settings: Optional[DocumentSummaryServiceSettings] = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._llm_invoker = llm_invoker
        self._document_context_provider = document_context_provider
        self._authorizer = authorizer
        self._settings = document_summary_service_settings or DocumentSummaryServiceSettings()
        self._pipeline = DocumentSummaryPipeline(
            plugins=self._build_pipeline_plugins(self._settings.pipeline_plugins),
        )
        logger.info("DocumentSummaryService initialized successfully")

    async def execute_document_summary(
            self,
            document_summary_request: DocumentSummaryRequest,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentSummaryResponse:
        logger.info(
            "Document summary execution initiated",
            extra={"user_id": authenticated_user.id, "document_id": document_summary_request.document_id},
        )

        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_DOCUMENT_SUMMARY}),
        )
        try:
            state = DocumentSummaryPipelineState.from_request(
                document_summary_request,
                authenticated_user=authenticated_user,
            )
            resources = DocumentSummaryPipelineResources(
                ollama_llm_facade=self._ollama_llm_facade,
                llm_invoker=self._llm_invoker,
                document_context_provider=self._document_context_provider,
            )

            await self._pipeline.run(state=state, resources=resources)

            logger.info(
                "Document summary execution completed",
                extra={"user_id": authenticated_user.id, "document_id": document_summary_request.document_id},
            )
            return DocumentSummaryResponse(
                document_id=state.document_id,
                summary=state.summary,
                fragments=state.fragments,
            )

        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during document summary execution",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise DocumentSummaryServiceException(
                "Unexpected error while processing the document summary"
            ) from e

    @staticmethod
    def _build_pipeline_plugins(plugin_names: list[str]) -> list[DocumentSummaryPlugin]:
        registry: dict[str, type[DocumentSummaryPlugin]] = {
            "validate_request": ValidateRequestPlugin,
            "retrieve_fragments": RetrieveFragmentsPlugin,
            "generate_summary_direct": GenerateSummaryDirectPlugin,
            "map_chunks": MapChunksPlugin,
            "reduce_summaries": ReduceSummariesPlugin,
            "fallback_summary": FallbackSummaryPlugin,
        }

        plugins: list[DocumentSummaryPlugin] = []
        for name in plugin_names:
            plugin_cls = registry.get(name)
            if plugin_cls is None:
                logger.warning(
                    "Unknown document_summary pipeline plugin",
                    extra={"plugin_name": name},
                )
                continue
            plugins.append(plugin_cls())

        return plugins


async def get_document_summary_service(request: Request) -> DocumentSummaryServiceInterface:
    try:
        return request.app.state.document_summary_service
    except AttributeError:
        logger.error("DocumentSummaryService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocumentSummaryService is not available",
        )
