import logging
from typing import Optional
from fastapi import HTTPException, Request, status

from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings,
)
from app.application.services.document_question_service.exceptions.document_question_service_exceptions import (
    DocumentQuestionServiceException,
)
from app.application.services.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface,
)
from app.domain.dtos.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question.document_question_response import DocumentQuestionResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

from app.application.services.document_question_service.pipeline.document_question_pipeline import (
    DocumentQuestionPipeline,
)
from app.application.services.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState,
)
from app.application.services.document_question_service.pipeline.document_question_pipeline_resources import (
    DocumentQuestionPipelineResources,
)
from app.application.services.document_question_service.interfaces.document_question_plugin_interface import (
    DocumentQuestionPlugin,
)
from app.application.services.document_question_service.plugins.validate_request_plugin import (
    ValidateRequestPlugin,
)
from app.application.services.document_question_service.plugins.rewrite_query_plugin import (
    RewriteQueryPlugin,
)
from app.application.services.document_question_service.plugins.retrieve_context_plugin import (
    RetrieveContextPlugin,
)
from app.application.services.document_question_service.plugins.rerank_context_plugin import (
    RerankContextPlugin,
)
from app.application.services.document_question_service.plugins.generate_answer_plugin import (
    GenerateAnswerPlugin,
)
from app.application.services.document_question_service.plugins.fallback_answer_plugin import (
    FallbackAnswerPlugin,
)

logger = logging.getLogger(__name__)


class DocumentQuestionService(DocumentQuestionServiceInterface):
    _KNOWN_EXCEPTIONS = (
        RequestValidationException,
        DocumentQuestionServiceException,
    )

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            document_question_service_settings: Optional[DocumentQuestionServiceSettings] = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._llm_invoker = llm_invoker
        self._document_context_provider = document_context_provider
        self._settings = document_question_service_settings or DocumentQuestionServiceSettings()

    async def execute_document_question(
            self,
            document_question_request: DocumentQuestionRequest,
            user: AuthenticationResponse,
            authorization: Optional[str] = None,
    ) -> DocumentQuestionResponse:
        logger.info("Document question execution initiated")

        try:
            state = DocumentQuestionPipelineState.from_request(
                document_question_request,
                authorization=authorization,
                user=user,
            )
            resources = DocumentQuestionPipelineResources(
                document_question_service_settings=self._settings,
                ollama_llm_facade=self._ollama_llm_facade,
                llm_invoker=self._llm_invoker,
                document_context_provider=self._document_context_provider,
            )

            pipeline = DocumentQuestionPipeline(
                plugins=self._build_pipeline_plugins(),
            )

            await pipeline.run(state=state, resources=resources)
            answer = state.response

            logger.info("Document question execution completed")
            return DocumentQuestionResponse(answer=answer)

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

    def _build_pipeline_plugins(self) -> list[DocumentQuestionPlugin]:
        default_order = [
            "validate_request",
            "rewrite_query",
            "retrieve_context",
            "rerank_context",
            "generate_answer",
            "fallback_answer",
        ]

        plugin_names = getattr(self._settings, "pipeline_plugins", None) or default_order

        registry: dict[str, type[DocumentQuestionPlugin]] = {
            "validate_request": ValidateRequestPlugin,
            "rewrite_query": RewriteQueryPlugin,
            "retrieve_context": RetrieveContextPlugin,
            "rerank_context": RerankContextPlugin,
            "generate_answer": GenerateAnswerPlugin,
            "fallback_answer": FallbackAnswerPlugin,
        }

        plugins: list[DocumentQuestionPlugin] = []
        for name in plugin_names:
            plugin_cls = registry.get(name)
            if plugin_cls is None:
                logger.warning(
                    "Unknown document_question pipeline plugin",
                    extra={"plugin_name": name},
                )
                continue
            plugins.append(plugin_cls())

        return plugins


async def get_document_question_service(request: Request) -> DocumentQuestionServiceInterface:
    try:
        return request.app.state.document_question_service
    except AttributeError:
        logger.error("DocumentQuestionService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocumentQuestionService is not available",
        )
