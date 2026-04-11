import logging
from collections.abc import AsyncIterator
from typing import Optional

from fastapi import HTTPException, Request, status

from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.general.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings,
)
from app.application.services.general.document_question_service.exceptions.document_question_service_exceptions import (
    DocumentQuestionServiceException,
)
from app.application.services.general.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.general.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.general.document_question.document_question_response import DocumentQuestionResponse
from app.domain.dtos.general.document_question.document_question_stream_events import (
    DocumentQuestionStreamComplete,
    DocumentQuestionStreamDelta,
    DocumentQuestionStreamError,
    DocumentQuestionStreamEvent,
    DocumentQuestionStreamMeta,
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

from app.application.services.general.document_question_service.pipeline.document_question_pipeline import (
    DocumentQuestionPipeline,
)
from app.application.services.general.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState,
)
from app.application.services.general.document_question_service.pipeline.document_question_pipeline_resources import (
    DocumentQuestionPipelineResources,
)
from app.application.services.general.document_question_service.interfaces.document_question_plugin_interface import (
    DocumentQuestionPlugin
)
from app.application.services.general.document_question_service.steps.validate_request.validate_request_plugin import (
    ValidateRequestPlugin,
)
from app.application.services.general.document_question_service.steps.rewrite_query.rewrite_query_plugin import (
    RewriteQueryPlugin,
)
from app.application.services.general.document_question_service.steps.retrieve_context.retrieve_context_plugin import (
    RetrieveContextPlugin,
)
from app.application.services.general.document_question_service.steps.rerank_context.rerank_context_plugin import (
    RerankContextPlugin,
)
from app.application.services.general.document_question_service.steps.generate_answer.generate_answer_llm_input import (
    build_generate_answer_llm_input,
)
from app.application.services.general.document_question_service.steps.generate_answer.generate_answer_plugin import (
    GenerateAnswerPlugin,
)
from app.application.services.general.document_question_service.steps.generate_answer.generate_answer_settings import (
    GenerateAnswerSettings,
)
from app.application.services.general.document_question_service.steps.fallback_answer.fallback_answer_plugin import (
    FallbackAnswerPlugin,
)

logger = logging.getLogger(__name__)

# Plugins run before streaming the main answer. Keep aligned with default
# DocumentQuestionServiceSettings.pipeline_plugins order (everything before generate_answer).
_STREAM_PRE_ANSWER_PLUGIN_NAMES: tuple[str, ...] = (
    "validate_request",
    "rewrite_query",
    "retrieve_context",
    "rerank_context",
)


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
            ollama_llm_streaming_invoker: OllamaLLMStreamingInvokerInterface,
            document_question_service_settings: Optional[DocumentQuestionServiceSettings] = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._llm_invoker = llm_invoker
        self._document_context_provider = document_context_provider
        self._llm_streaming_invoker = ollama_llm_streaming_invoker
        self._settings = document_question_service_settings or DocumentQuestionServiceSettings()
        self._pipeline = DocumentQuestionPipeline(
            plugins=self._build_pipeline_plugins(self._settings.pipeline_plugins),
        )
        self._stream_pre_answer_pipeline = DocumentQuestionPipeline(
            plugins=self._build_stream_pre_answer_plugins(),
        )

    async def execute_document_question(
            self,
            document_question_request: DocumentQuestionRequest,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentQuestionResponse:
        logger.info("Document question execution initiated")

        try:
            state = DocumentQuestionPipelineState.from_request(
                document_question_request,
                authenticated_user=authenticated_user,
            )
            resources = DocumentQuestionPipelineResources(
                ollama_llm_facade=self._ollama_llm_facade,
                llm_invoker=self._llm_invoker,
                document_context_provider=self._document_context_provider,
            )

            await self._pipeline.run(state=state, resources=resources)

            logger.info("Document question execution completed")
            return DocumentQuestionResponse(
                question=state.current_message.content,
                answer=state.answer,
                fragments=state.rerank_fragments or state.retrieved_fragments
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
            state = DocumentQuestionPipelineState.from_request(
                document_question_request,
                authenticated_user=authenticated_user,
            )
            resources = DocumentQuestionPipelineResources(
                ollama_llm_facade=self._ollama_llm_facade,
                llm_invoker=self._llm_invoker,
                document_context_provider=self._document_context_provider,
            )
            await self._stream_pre_answer_pipeline.run(state=state, resources=resources)

            fragments = state.rerank_fragments or state.retrieved_fragments
            yield DocumentQuestionStreamMeta(
                question=state.current_message.content,
                fragments=list(fragments),
            )

            has_context = bool(fragments)
            state.answer = ""

            if has_context:
                generate_settings = GenerateAnswerSettings()
                llm_input = build_generate_answer_llm_input(
                    state,
                    generate_settings.history_window,
                )
                try:
                    llm = await self._ollama_llm_facade.get_llm_base()
                    async for delta in self._llm_streaming_invoker.stream_llm_content(
                            llm,
                            llm_input,
                    ):
                        state.answer += delta
                        yield DocumentQuestionStreamDelta(text=delta)
                except LLMInvocationError as e:
                    logger.exception("LLM streaming failed for document question")
                    yield DocumentQuestionStreamError(
                        message=str(e),
                        code=type(e).__name__,
                    )
                    return
                except Exception as e:
                    logger.exception(
                        "Failed to stream answer",
                        extra={"error_type": type(e).__name__},
                    )
                    yield DocumentQuestionStreamError(
                        message="Error invoking the language model",
                        code="StreamAnswerError",
                    )
                    return

            state.answer = state.answer.strip() if state.answer else ""

            if not has_context or not state.answer:
                fallback = FallbackAnswerPlugin()
                if fallback.should_run(state=state, resources=resources):
                    await fallback.run(state=state, resources=resources)

            yield DocumentQuestionStreamComplete(
                result=DocumentQuestionResponse(
                    question=state.current_message.content,
                    answer=state.answer,
                    fragments=fragments,
                ),
            )

        except RequestValidationException as e:
            yield DocumentQuestionStreamError(message=e.message, code=e.code)
            return
        except DocumentQuestionServiceException as e:
            yield DocumentQuestionStreamError(message=e.message, code=e.code)
            return
        except Exception as e:
            logger.exception(
                "Unexpected error during document question stream",
                extra={"error_type": type(e).__name__},
            )
            yield DocumentQuestionStreamError(
                message="Unexpected error while processing the question",
                code="DocumentQuestionStreamError",
            )
            return

    @staticmethod
    def _build_pipeline_plugins(plugin_names: list[str]) -> list[DocumentQuestionPlugin]:
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

    @staticmethod
    def _build_stream_pre_answer_plugins() -> list[DocumentQuestionPlugin]:
        registry: dict[str, type[DocumentQuestionPlugin]] = {
            "validate_request": ValidateRequestPlugin,
            "rewrite_query": RewriteQueryPlugin,
            "retrieve_context": RetrieveContextPlugin,
            "rerank_context": RerankContextPlugin,
        }
        plugins: list[DocumentQuestionPlugin] = []
        for name in _STREAM_PRE_ANSWER_PLUGIN_NAMES:
            plugin_cls = registry.get(name)
            if plugin_cls is None:
                logger.warning(
                    "Unknown stream pre-answer plugin name",
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
