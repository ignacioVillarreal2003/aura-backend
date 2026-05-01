import asyncio
import logging
from typing import Optional
from fastapi import HTTPException, Request, status

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.authorization.permissions import Permissions
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.agent_service.agent_settings import AgentServiceSettings
from app.application.services.agent_service.agent_state.agent_state import AgentState
from app.application.services.agent_service.agent_state.agent_state_builder import AgentStateBuilder
from app.application.services.agent_service.agent_workflow import AgentWorkflow
from app.application.services.agent_service.exceptions.agent_service_exceptions import AgentServiceException
from app.application.services.agent_service.interfaces.agent_service_interface import AgentServiceInterface
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.agent.agent_request import AgentRequest
from app.domain.dtos.agent.agent_response import AgentResponse
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


class AgentService(AgentServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            document_context_provider: DocumentContextProviderInterface,
            authorizer: Authorizer,
            agent_service_settings: Optional[AgentServiceSettings] = None,
    ) -> None:
        self._authorizer = authorizer
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

        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_AGENT}),
        )

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

        return AgentResponse(
            messages=[Message(role=MessageRole.assistant, content=answer)]
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
