import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Optional
from fastapi import HTTPException, Request, status

from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.user_interactions.agent_service.agent_settings import AgentServiceSettings
from app.application.services.user_interactions.agent_service.agent_state.agent_state import AgentState
from app.application.services.user_interactions.agent_service.agent_state.agent_state_builder import AgentStateBuilder
from app.application.services.user_interactions.agent_service.agent_workflow import AgentWorkflow
from app.application.services.user_interactions.agent_service.constants.node_name import NodeName
from app.application.services.user_interactions.agent_service.exceptions.agent_service_exceptions import AgentServiceException
from app.application.services.user_interactions.agent_service.interfaces.agent_service_interface import AgentServiceInterface
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
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)

_FALLBACK_ANSWER = (
    "No se pudo procesar la consulta en este momento. "
    "Por favor, intente nuevamente más tarde."
)

_KNOWN_EXCEPTIONS = (
    RequestValidationException,
    AgentServiceException,
    UnauthorizedException,
)

_STREAM_PROGRESS_MESSAGES: dict[str, tuple[str, str]] = {
    NodeName.input_normalizer.value: (
        NodeName.input_normalizer.value,
        "Procesando la consulta...",
    ),
    NodeName.context_resolver.value: (
        NodeName.context_resolver.value,
        "Reformulando la consulta según el contexto del chat...",
    ),
    NodeName.intent_classifier.value: (
        NodeName.intent_classifier.value,
        "Identificando la intención de la consulta...",
    ),
    NodeName.keyword_extractor.value: (
        NodeName.keyword_extractor.value,
        "Extrayendo términos clave para la búsqueda...",
    ),
    NodeName.retriever.value: (
        NodeName.retriever.value,
        "Buscando información relevante en los documentos...",
    ),
    NodeName.document_fetcher.value: (
        NodeName.document_fetcher.value,
        "Recuperando el documento solicitado...",
    ),
    NodeName.context_builder.value: (
        NodeName.context_builder.value,
        "Preparando el contexto para la respuesta...",
    ),
    NodeName.answer_generator.value: (
        NodeName.answer_generator.value,
        "Redactando la respuesta...",
    ),
    NodeName.guardrails.value: (
        NodeName.guardrails.value,
        "Validando la calidad de la respuesta...",
    ),
    NodeName.fallback.value: (
        NodeName.fallback.value,
        "No se encontró información relevante. Generando respuesta alternativa...",
    ),
}


class AgentService(AgentServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            document_context_provider: DocumentContextProviderInterface,
            agent_service_settings: Optional[AgentServiceSettings] = None,
    ) -> None:
        self._agent_service_settings = agent_service_settings or AgentServiceSettings()

        self._agent_workflow = AgentWorkflow(
            ollama_llm_facade=ollama_llm_facade,
            document_context_provider=document_context_provider,
            agent_service_settings=self._agent_service_settings,
        )
        self._workflow_built = False
        self._workflow_lock = asyncio.Lock()
        self._agent_state_builder = AgentStateBuilder()

        logger.info("AgentService initialized")

    async def execute_agent(
            self,
            agent_request: AgentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AgentResponse:
        logger.info("Agent execution initiated", extra={"user_id": authenticated_user.id})
        try:
            await self._ensure_workflow_built()

            initial_state = self._agent_state_builder.build_agent_state(
                agent_request=agent_request,
                authenticated_user=authenticated_user,
            )
            final_state = await self._agent_workflow.invoke(initial_state)

            logger.info("Agent execution completed", extra={"user_id": authenticated_user.id})
            return self._build_response(final_state)

        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during agent execution",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise AgentServiceException(
                message=f"Unexpected error executing the agent: {e}",
                status_code=500,
            ) from e

    async def execute_agent_stream(
            self,
            agent_request: AgentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[AgentStreamEvent]:
        logger.info("Agent stream initiated", extra={"user_id": authenticated_user.id})

        try:
            await self._ensure_workflow_built()
        except Exception:
            logger.exception("Failed to build workflow for streaming")
            yield AgentStreamError(message="Error al inicializar el servicio.", code="workflow_build_error")
            return

        try:
            initial_state = self._agent_state_builder.build_agent_state(
                agent_request=agent_request,
                authenticated_user=authenticated_user,
            )

            async for event_type, data in self._agent_workflow.stream(initial_state):
                if event_type == "progress":
                    step, message = _STREAM_PROGRESS_MESSAGES.get(
                        data, (data, f"Procesando {data}...")
                    )
                    yield AgentStreamProgress(step=step, message=message)
                elif event_type == "done":
                    result = self._build_response(data)
                    yield AgentStreamComplete(result=result)
                    logger.info("Agent stream completed", extra={"user_id": authenticated_user.id})
                elif event_type == "error":
                    logger.error("Agent workflow stream error", exc_info=data)
                    yield AgentStreamError(message="Error procesando la consulta.", code="workflow_error")

        except _KNOWN_EXCEPTIONS as e:
            logger.warning(
                "Known error during agent stream",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            yield AgentStreamError(message=str(e), code=type(e).__name__)
        except Exception:
            logger.exception("Unexpected error during agent stream")
            yield AgentStreamError(message="Error inesperado al procesar la consulta.", code="unexpected_error")

    async def _ensure_workflow_built(self) -> None:
        if self._workflow_built:
            return
        async with self._workflow_lock:
            if self._workflow_built:
                return
            await self._agent_workflow.build()
            self._workflow_built = True

    @staticmethod
    def _build_response(final_state: AgentState) -> AgentResponse:
        answer = final_state.get("answer", "").strip()
        if not answer:
            answer = _FALLBACK_ANSWER
        answer = answer[:MAX_MESSAGE_CONTENT_CHARS]
        fragments = final_state.get("retrieved_fragments") or []
        return AgentResponse(
            messages=[Message(role=MessageRole.assistant, content=answer)],
            fragments=fragments,
        )


async def get_agent_service(request: Request) -> AgentServiceInterface:
    try:
        return request.app.state.agent_service
    except AttributeError:
        logger.error("AgentService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent service is not available",
        )
