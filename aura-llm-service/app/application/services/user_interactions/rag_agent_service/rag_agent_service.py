import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Optional


from app.application.authorization.exceptions.authorization_exceptions import UnauthorizedException
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.generation_shared.generation_observability import (
    generation_seconds,
    generation_total,
)
from app.application.services.user_interactions.rag_agent_service.constants.rag_node_name import RagNodeName
from app.application.services.user_interactions.rag_agent_service.exceptions.rag_agent_service_exceptions import RagAgentServiceException
from app.application.services.user_interactions.rag_agent_service.interfaces.rag_agent_service_interface import RagAgentServiceInterface
from app.application.services.user_interactions.rag_agent_service.rag_agent_settings import RagAgentServiceSettings
from app.application.services.user_interactions.rag_agent_service.rag_agent_state.rag_agent_state import RagAgentState
from app.application.services.user_interactions.rag_agent_service.rag_agent_state.rag_agent_state_builder import RagAgentStateBuilder
from app.application.services.user_interactions.rag_agent_service.rag_agent_workflow import RagAgentWorkflow
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.user_interactions.agent.agent_request import AgentRequest
from app.domain.dtos.user_interactions.agent.agent_response import AgentResponse
from app.domain.dtos.user_interactions.agent.agent_stream_events import (
    AgentStreamComplete,
    AgentStreamError,
    AgentStreamEvent,
    AgentStreamProgress,
)
from app.domain.dtos.message import Message
from app.domain.field_limits import MAX_MESSAGE_CONTENT_CHARS
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.http.graph_context_provider.interfaces.graph_context_provider_interface import (
    GraphContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_FALLBACK_ANSWER = (
    "No se pudo procesar la consulta en este momento. "
    "Por favor, intente nuevamente más tarde."
)

_INITIAL_PROGRESS_STEP = "processing"
_INITIAL_PROGRESS_MESSAGE = "Procesando tu consulta..."

_METRIC_LABEL = "rag-agent"


def _record_metrics(call_mode: str, outcome: str, started: float) -> None:
    try:
        generation_seconds.labels(label=_METRIC_LABEL, call_mode=call_mode).observe(
            time.perf_counter() - started
        )
        generation_total.labels(label=_METRIC_LABEL, call_mode=call_mode, outcome=outcome).inc()
    except Exception:
        logger.debug("Failed to record RAG agent metrics.", exc_info=True)

_KNOWN_EXCEPTIONS = (
    RequestValidationException,
    RagAgentServiceException,
    UnauthorizedException,
)

_STREAM_PROGRESS_MESSAGES: dict[str, tuple[str, str]] = {
    RagNodeName.query_analyzer.value: (
        RagNodeName.query_analyzer.value,
        "Analizando y reformulando la consulta...",
    ),
    RagNodeName.graph_context_retriever.value: (
        RagNodeName.graph_context_retriever.value,
        "Consultando el grafo de conocimiento...",
    ),
    RagNodeName.context_retriever.value: (
        RagNodeName.context_retriever.value,
        "Buscando información relevante en los documentos...",
    ),
    RagNodeName.document_fetcher.value: (
        RagNodeName.document_fetcher.value,
        "Recuperando el contenido completo de los documentos...",
    ),
    RagNodeName.context_grader.value: (
        RagNodeName.context_grader.value,
        "Evaluando si el contexto recuperado es suficiente...",
    ),
    RagNodeName.query_refiner.value: (
        RagNodeName.query_refiner.value,
        "Refinando la consulta para mejorar la búsqueda...",
    ),
    RagNodeName.answer_synthesizer.value: (
        RagNodeName.answer_synthesizer.value,
        "Elaborando la respuesta con el contexto encontrado...",
    ),
    RagNodeName.guardrails.value: (
        RagNodeName.guardrails.value,
        "Verificando la calidad y seguridad de la respuesta...",
    ),
    RagNodeName.fallback.value: (
        RagNodeName.fallback.value,
        "No se encontró información relevante. Generando respuesta alternativa...",
    ),
}


class RagAgentService(RagAgentServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            rag_agent_settings: Optional[RagAgentServiceSettings] = None,
            graph_context_provider: Optional[GraphContextProviderInterface] = None,
    ) -> None:
        self._rag_agent_settings = rag_agent_settings or RagAgentServiceSettings()

        self._workflow = RagAgentWorkflow(
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
            document_context_provider=document_context_provider,
            settings=self._rag_agent_settings,
            graph_context_provider=graph_context_provider,
        )
        self._workflow_built = False
        self._workflow_lock = asyncio.Lock()
        self._state_builder = RagAgentStateBuilder()

        logger.info("RagAgentService initialized")

    async def execute(
            self,
            agent_request: AgentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AgentResponse:
        logger.info("RAG agent execution initiated", extra={"user_id": authenticated_user.id})
        started = time.perf_counter()
        outcome = "error"
        try:
            await self._ensure_workflow_built()

            initial_state = self._state_builder.build(
                agent_request=agent_request,
                authenticated_user=authenticated_user,
            )
            final_state = await self._workflow.invoke(initial_state)

            outcome = "fallback" if final_state.get("fallback_triggered") else "success"
            logger.info("RAG agent execution completed", extra={"user_id": authenticated_user.id})
            return self._build_response(final_state)

        except _KNOWN_EXCEPTIONS:
            outcome = "known_error"
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during RAG agent execution",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise RagAgentServiceException(
                "Unexpected error while processing the RAG agent request",
                status_code=500,
            ) from e
        finally:
            _record_metrics("sync", outcome, started)

    async def execute_stream(
            self,
            agent_request: AgentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[AgentStreamEvent]:
        logger.info("RAG agent stream initiated", extra={"user_id": authenticated_user.id})
        started = time.perf_counter()

        try:
            await self._ensure_workflow_built()
        except Exception:
            logger.exception("Failed to build workflow for streaming")
            _record_metrics("stream", "build_error", started)
            yield AgentStreamError(message="Error al inicializar el servicio.", code="workflow_build_error")
            return

        outcome = "error"
        try:
            yield AgentStreamProgress(
                step=_INITIAL_PROGRESS_STEP,
                message=_INITIAL_PROGRESS_MESSAGE,
            )

            initial_state = self._state_builder.build(
                agent_request=agent_request,
                authenticated_user=authenticated_user,
            )

            async for event_type, data in self._workflow.stream(initial_state):
                if event_type == "progress":
                    step, message = _STREAM_PROGRESS_MESSAGES.get(
                        data, (data, f"Procesando {data}...")
                    )
                    yield AgentStreamProgress(step=step, message=message)
                elif event_type == "done":
                    result = self._build_response(data)
                    outcome = "fallback" if data.get("fallback_triggered") else "success"
                    yield AgentStreamComplete(result=result)
                    logger.info("RAG agent stream completed", extra={"user_id": authenticated_user.id})
                elif event_type == "error":
                    outcome = "error"
                    logger.error("RAG workflow stream error", exc_info=data)
                    yield AgentStreamError(message="Error procesando la consulta.", code="workflow_error")

        except _KNOWN_EXCEPTIONS as e:
            outcome = "known_error"
            logger.warning(
                "Known error during RAG agent stream",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            yield AgentStreamError(message=str(e), code=type(e).__name__)
        except Exception:
            logger.exception("Unexpected error during RAG agent stream")
            yield AgentStreamError(message="Error inesperado al procesar la consulta.", code="unexpected_error")
        finally:
            _record_metrics("stream", outcome, started)

    async def _ensure_workflow_built(self) -> None:
        if self._workflow_built:
            return
        async with self._workflow_lock:
            if self._workflow_built:
                return
            await self._workflow.build()
            self._workflow_built = True

    @staticmethod
    def _build_response(final_state: RagAgentState) -> AgentResponse:
        answer = final_state.get("answer", "").strip()
        if not answer:
            answer = _FALLBACK_ANSWER
        answer = answer[:MAX_MESSAGE_CONTENT_CHARS]
        fragments = final_state.get("retrieved_fragments") or []
        return AgentResponse(
            messages=[Message(role=MessageRole.assistant, content=answer)],
            fragments=fragments,
        )

