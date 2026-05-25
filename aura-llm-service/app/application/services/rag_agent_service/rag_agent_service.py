import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Optional

from fastapi import HTTPException, Request, status

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.authorization.permissions import Permissions
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.rag_agent_service.constants.rag_node_name import RagNodeName
from app.application.services.rag_agent_service.exceptions.rag_agent_service_exceptions import RagAgentServiceException
from app.application.services.rag_agent_service.interfaces.rag_agent_service_interface import RagAgentServiceInterface
from app.application.services.rag_agent_service.rag_agent_settings import RagAgentServiceSettings
from app.application.services.rag_agent_service.rag_agent_state.rag_agent_state import RagAgentState
from app.application.services.rag_agent_service.rag_agent_state.rag_agent_state_builder import RagAgentStateBuilder
from app.application.services.rag_agent_service.rag_agent_workflow import RagAgentWorkflow
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.agent.agent_request import AgentRequest
from app.domain.dtos.agent.agent_response import AgentResponse
from app.domain.dtos.agent.agent_stream_events import (
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
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)

_FALLBACK_ANSWER = (
    "No se pudo procesar la consulta en este momento. "
    "Por favor, intente nuevamente más tarde."
)

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
    RagNodeName.context_retriever.value: (
        RagNodeName.context_retriever.value,
        "Recuperando contexto documental...",
    ),
    RagNodeName.answer_synthesizer.value: (
        RagNodeName.answer_synthesizer.value,
        "Sintetizando la respuesta...",
    ),
    RagNodeName.fallback.value: (
        RagNodeName.fallback.value,
        "No se encontró contexto relevante. Preparando respuesta alternativa...",
    ),
}


class RagAgentService(RagAgentServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            document_context_provider: DocumentContextProviderInterface,
            authorizer: Authorizer,
            settings: Optional[RagAgentServiceSettings] = None,
    ) -> None:
        self._authorizer = authorizer
        self._settings = settings or RagAgentServiceSettings()

        self._workflow = RagAgentWorkflow(
            ollama_llm_facade=ollama_llm_facade,
            document_context_provider=document_context_provider,
            settings=self._settings,
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

        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_AGENT}),
        )

        try:
            await self._ensure_workflow_built()

            initial_state = self._state_builder.build(
                agent_request=agent_request,
                authenticated_user=authenticated_user,
            )
            final_state = await self._workflow.invoke(initial_state)

            logger.info("RAG agent execution completed", extra={"user_id": authenticated_user.id})
            return self._build_response(final_state)

        except _KNOWN_EXCEPTIONS:
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

    async def execute_stream(
            self,
            agent_request: AgentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[AgentStreamEvent]:
        logger.info("RAG agent stream initiated", extra={"user_id": authenticated_user.id})

        try:
            await self._ensure_workflow_built()
        except Exception as e:
            logger.exception("Failed to build workflow for streaming")
            yield AgentStreamError(message="Error al inicializar el servicio.", code="workflow_build_error")
            return

        initial_state = self._state_builder.build(
            agent_request=agent_request,
            authenticated_user=authenticated_user,
        )

        try:
            async for event_type, data in self._workflow.stream(initial_state):
                if event_type == "progress":
                    step, message = _STREAM_PROGRESS_MESSAGES.get(
                        data, (data, f"Procesando {data}...")
                    )
                    yield AgentStreamProgress(step=step, message=message)
                elif event_type == "done":
                    result = self._build_response(data)
                    yield AgentStreamComplete(result=result)
                    logger.info("RAG agent stream completed", extra={"user_id": authenticated_user.id})
                elif event_type == "error":
                    logger.error("RAG workflow stream error", exc_info=data)
                    yield AgentStreamError(message="Error procesando la consulta.", code="workflow_error")
        except _KNOWN_EXCEPTIONS:
            raise
        except Exception:
            logger.exception("Unexpected error during RAG agent stream")
            yield AgentStreamError(message="Error inesperado al procesar la consulta.", code="unexpected_error")

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


async def get_rag_agent_service(request: Request) -> RagAgentServiceInterface:
    try:
        return request.app.state.rag_agent_service
    except AttributeError:
        logger.error("RagAgentService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG agent service is not available",
        )
