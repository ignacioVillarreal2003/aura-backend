import logging
from collections.abc import Awaitable, Callable
from typing import Any
from fastapi import FastAPI

from app.application.services.user_interactions.document_action_service.document_action_service import \
    DocumentActionService
from app.application.services.user_interactions.document_summary_service.document_summary_service import \
    DocumentSummaryService
from app.application.services.user_interactions.document_question_service.document_question_service import \
    DocumentQuestionService
from app.application.services.processing.document_classify_service.document_classify_service import \
    DocumentClassifyService
from app.application.services.processing.fragment_enrich_service.fragment_enrich_service import FragmentEnrichService
from app.application.services.processing.graph_extraction_service.graph_extraction_service import GraphExtractionService
from app.application.services.processing.graph_query_translation_service.graph_query_translation_service import (
    GraphQueryTranslationService,
)
from app.application.services.user_interactions.general_chat_service.general_chat_service import GeneralChatService
from app.application.services.user_interactions.rag_agent_service.rag_agent_service import RagAgentService
from app.application.services.user_interactions.report_service.report_service import ReportService
from app.application.services.user_interactions.checklist_service.checklist_service import ChecklistService
from app.application.services.user_interactions.timeline_service.timeline_service import TimelineService
from app.application.services.user_interactions.quiz_service.quiz_service import QuizService
from app.application.services.user_interactions.lessons_learned_service.lessons_learned_service import \
    LessonsLearnedService
from app.application.services.user_interactions.decision_brief_service.decision_brief_service import \
    DecisionBriefService
from app.infrastructure.guardrails.nemo_guardrails_service import NemoGuardrailsService
from app.infrastructure.http.authentication_provider.authentication_provider import AuthenticationProvider
from app.infrastructure.http.document_context_provider.document_context_provider import DocumentContextProvider
from app.infrastructure.http.graph_context_provider.graph_context_provider import GraphContextProvider
from app.infrastructure.http.http_client.http_client import HttpClient
from app.infrastructure.persistence.memory_database.redis_client.redis_client import RedisClient
from app.infrastructure.llm.ollama_llm.ollama_llm_facade import OllamaLLMFacade
from app.infrastructure.llm.ollama_llm.ollama_llm_facade_settings import OllamaLLMFacadeSettings
from app.infrastructure.llm.ollama_llm.ollama_llm_invoker import OllamaLLMInvoker
from app.infrastructure.llm.ollama_llm.ollama_llm_invoker_settings import OllamaLLMInvokerSettings
from app.infrastructure.llm.ollama_llm.ollama_llm_streaming_invoker import OllamaLLMStreamingInvoker

logger = logging.getLogger(__name__)

_CleanupFn = Callable[[], Awaitable[None]]


class _DependencyRegistry:
    def __init__(self, app: FastAPI) -> None:
        self._app = app
        self._registered: list[str] = []
        self._cleanups: list[tuple[str, _CleanupFn]] = []

    def register(self, name: str, instance: Any, cleanup: _CleanupFn | None = None) -> None:
        setattr(self._app.state, name, instance)
        self._registered.append(name)
        if cleanup is not None:
            self._cleanups.append((name, cleanup))

    def commit(self) -> None:
        self._registered.clear()
        self._cleanups.clear()

    async def rollback(self) -> None:
        while self._cleanups:
            name, cleanup = self._cleanups.pop()
            try:
                await cleanup()
            except Exception:
                logger.exception(
                    "Startup rollback: cleanup step failed (continuing with remaining steps).",
                    extra={"resource": name},
                )

        for name in reversed(self._registered):
            if hasattr(self._app.state, name):
                delattr(self._app.state, name)
        self._registered.clear()


async def startup_dependencies(app: FastAPI) -> None:
    registry = _DependencyRegistry(app)

    try:
        logger.info("Starting up dependencies")

        http_client = HttpClient()
        await http_client.start()
        registry.register("http_client", http_client, cleanup=http_client.stop)

        redis_client = RedisClient()
        await redis_client.initialize()
        registry.register("redis_client", redis_client, cleanup=redis_client.dispose)

        registry.register(
            "authentication_provider",
            AuthenticationProvider(http_client=http_client, redis_client=redis_client.client),
        )

        document_context_provider = DocumentContextProvider(http_client=http_client)
        registry.register("document_context_provider", document_context_provider)

        graph_context_provider = GraphContextProvider(http_client=http_client)
        registry.register("graph_context_provider", graph_context_provider)

        ollama_facade = OllamaLLMFacade(ollama_llm_facade_settings=OllamaLLMFacadeSettings())
        await ollama_facade.initialize()
        registry.register("ollama_llm_facade", ollama_facade)

        registry.register("nemo_guardrails", NemoGuardrailsService(ollama_llm_facade=ollama_facade))

        invoker_settings = OllamaLLMInvokerSettings()
        ollama_llm_invoker = OllamaLLMInvoker(settings=invoker_settings)
        ollama_llm_streaming_invoker = OllamaLLMStreamingInvoker(settings=invoker_settings)

        streaming_service_kwargs = {
            "ollama_llm_facade": ollama_facade,
            "ollama_llm_invoker": ollama_llm_invoker,
            "ollama_llm_streaming_invoker": ollama_llm_streaming_invoker,
            "document_context_provider": document_context_provider,
        }
        generation_service_kwargs = {
            "ollama_llm_facade": ollama_facade,
            "ollama_llm_invoker": ollama_llm_invoker,
            "document_context_provider": document_context_provider,
        }
        processing_service_kwargs = {
            "ollama_llm_facade": ollama_facade,
            "ollama_llm_invoker": ollama_llm_invoker,
        }

        registry.register("document_question_service", DocumentQuestionService(**streaming_service_kwargs))
        registry.register("document_summary_service", DocumentSummaryService(**streaming_service_kwargs))
        registry.register("document_action_service", DocumentActionService(**streaming_service_kwargs))
        registry.register("general_chat_service", GeneralChatService(**streaming_service_kwargs))

        registry.register("document_classify_service", DocumentClassifyService(**processing_service_kwargs))
        registry.register("fragment_enrich_service", FragmentEnrichService(**processing_service_kwargs))
        registry.register("graph_extraction_service", GraphExtractionService(**processing_service_kwargs))
        registry.register(
            "graph_query_translation_service", GraphQueryTranslationService(**processing_service_kwargs)
        )

        registry.register(
            "rag_agent_service",
            RagAgentService(
                ollama_llm_facade=ollama_facade,
                document_context_provider=document_context_provider,
                graph_context_provider=graph_context_provider,
            ),
        )

        registry.register("report_service", ReportService(**generation_service_kwargs))
        registry.register("checklist_service", ChecklistService(**generation_service_kwargs))
        registry.register("timeline_service", TimelineService(**generation_service_kwargs))
        registry.register("quiz_service", QuizService(**generation_service_kwargs))
        registry.register("lessons_learned_service", LessonsLearnedService(**generation_service_kwargs))
        registry.register("decision_brief_service", DecisionBriefService(**generation_service_kwargs))

        logger.info("All dependencies started successfully")
        registry.commit()

    except Exception:
        logger.critical("Error during dependency startup; rolling back started resources in reverse order.")
        await registry.rollback()
        raise


async def shutdown_dependencies(app: FastAPI) -> None:
    logger.info("Shutting down dependencies")

    state = app.state

    if http_client := getattr(state, "http_client", None):
        await http_client.stop()

    if redis_client := getattr(state, "redis_client", None):
        await redis_client.dispose()

    logger.info("All dependencies shut down successfully")
