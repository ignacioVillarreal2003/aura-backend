import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from langchain_core.tools import BaseTool

from app.application.authorization.authorizer import Authorizer
from app.application.services.document.document_action_service.document_action_service import DocumentActionService
from app.application.services.document.document_summary_service.document_summary_service import DocumentSummaryService
from app.application.services.general.agent_service.agent_service import AgentService
from app.application.services.general.agent_service.tools.document_question_tool.document_question_tool import (
    DocumentQuestionTool
)
from app.application.services.general.agent_service.tools.document_summary_tool.document_summary_tool import (
    DocumentSummaryTool
)
from app.application.services.general.document_question_service.document_question_service import DocumentQuestionService
from app.application.services.general.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings,
)
from app.application.services.support.document_classify_service.document_classify_service import DocumentClassifyService
from app.application.services.support.fragment_enrich_service.fragment_enrich_service import FragmentEnrichService
from app.infrastructure.http.authentication_provider.authentication_provider import AuthenticationProvider
from app.infrastructure.http.document_context_provider.document_context_provider import DocumentContextProvider
from app.infrastructure.http.http_client.http_client import HttpClient
from app.infrastructure.llm.ollama_llm.ollama_llm_facade import OllamaLLMFacade
from app.infrastructure.llm.ollama_llm.ollama_llm_facade_settings import OllamaLLMFacadeSettings
from app.infrastructure.llm.ollama_llm.ollama_llm_invoker import OllamaLLMInvoker
from app.infrastructure.llm.ollama_llm.ollama_llm_invoker_settings import OllamaLLMInvokerSettings
from app.infrastructure.llm.ollama_llm.ollama_llm_streaming_invoker import OllamaLLMStreamingInvoker

logger = logging.getLogger(__name__)


_CleanupFn = Callable[[], Awaitable[None]]


async def _rollback_partial_startup(
        *,
        cleanup_stack: list[tuple[str, _CleanupFn]],
        app: FastAPI,
) -> None:
    while cleanup_stack:
        name, fn = cleanup_stack.pop()
        try:
            await fn()
        except Exception:
            logger.exception(
                "Startup rollback: cleanup step failed (continuing with remaining steps).",
                extra={"resource": name},
            )

    to_clear = [
        "agent_service",
        "fragment_enrich_service",
        "document_classify_service",
        "document_action_service",
        "document_summary_service",
        "document_question_service",
        "ollama_llm_facade",
        "document_context_provider",
        "authorizer",
        "authentication_provider",
        "http_client",
    ]
    for attr in to_clear:
        if hasattr(app.state, attr):
            delattr(app.state, attr)


async def startup_dependencies(app: FastAPI) -> None:
    cleanup_stack: list[tuple[str, _CleanupFn]] = []

    try:
        logger.info("Starting up dependencies")

        http_client = HttpClient()
        await http_client.start()
        app.state.http_client = http_client
        cleanup_stack.append(("http_client", http_client.stop))

        authentication_provider = AuthenticationProvider(http_client=http_client)
        app.state.authentication_provider = authentication_provider

        authorizer = Authorizer()
        app.state.authorizer = authorizer

        document_context_provider = DocumentContextProvider(http_client=http_client)
        app.state.document_context_provider = document_context_provider

        ollama_settings = OllamaLLMFacadeSettings()
        ollama_facade = OllamaLLMFacade(ollama_llm_facade_settings=ollama_settings)
        await ollama_facade.initialize()
        app.state.ollama_llm_facade = ollama_facade

        invoker_settings = OllamaLLMInvokerSettings()
        ollama_llm_invoker = OllamaLLMInvoker(settings=invoker_settings)
        ollama_llm_streaming_invoker = OllamaLLMStreamingInvoker(settings=invoker_settings)

        document_question_service_settings = DocumentQuestionServiceSettings()
        document_question_service = DocumentQuestionService(
            ollama_llm_facade=ollama_facade,
            llm_invoker=ollama_llm_invoker,
            document_context_provider=document_context_provider,
            ollama_llm_streaming_invoker=ollama_llm_streaming_invoker,
            document_question_service_settings=document_question_service_settings,
            authorizer=authorizer,
        )
        app.state.document_question_service = document_question_service

        document_summary_service = DocumentSummaryService(
            ollama_llm_facade=ollama_facade,
            llm_invoker=ollama_llm_invoker,
            document_context_provider=document_context_provider,
            authorizer=authorizer,
        )
        app.state.document_summary_service = document_summary_service

        document_action_service = DocumentActionService(
            ollama_llm_facade=ollama_facade,
            llm_invoker=ollama_llm_invoker,
            document_context_provider=document_context_provider,
            authorizer=authorizer,
        )
        app.state.document_action_service = document_action_service

        document_classify_service = DocumentClassifyService(
            ollama_llm_facade=ollama_facade,
            llm_invoker=ollama_llm_invoker,
            authorizer=authorizer,
        )
        app.state.document_classify_service = document_classify_service

        fragment_enrich_service = FragmentEnrichService(
            ollama_llm_facade=ollama_facade,
            llm_invoker=ollama_llm_invoker,
            authorizer=authorizer,
        )
        app.state.fragment_enrich_service = fragment_enrich_service

        def make_question_tool() -> BaseTool:
            return DocumentQuestionTool(document_question_service=document_question_service)

        def make_summary_tool() -> BaseTool:
            return DocumentSummaryTool(document_summary_service=document_summary_service)

        ollama_facade.register_tools([make_question_tool, make_summary_tool])

        agent_service = AgentService(
            ollama_llm_facade=ollama_facade,
            authorizer=authorizer,
        )
        app.state.agent_service = agent_service

        logger.info("All dependencies started successfully")
        cleanup_stack.clear()

    except Exception:
        logger.critical("Error during dependency startup; rolling back started resources in reverse order.")
        await _rollback_partial_startup(cleanup_stack=cleanup_stack, app=app)
        raise


async def shutdown_dependencies(app: FastAPI) -> None:
    logger.info("Shutting down dependencies")

    state = app.state

    if http_client := getattr(state, "http_client", None):
        await http_client.stop()

    logger.info("All dependencies shut down successfully")
