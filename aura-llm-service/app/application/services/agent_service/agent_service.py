import logging
from typing import Optional
from fastapi import HTTPException, Request, status

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.authorization.permissions import Permissions
from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.agent_service.agent_configuration import AgentConfiguration
from app.application.services.agent_service.agent_node.agent_node_configuration import AgentNodeConfiguration
from app.application.services.agent_service.agent_request_validator import AgentRequestValidator
from app.application.services.agent_service.agent_state.agent_state_builder import AgentStateBuilder
from app.application.services.agent_service.agent_workflow import AgentWorkflow
from app.application.services.agent_service.exceptions.agent_service_exceptions import AgentServiceException
from app.application.services.agent_service.interfaces.agent_service_interface import AgentServiceInterface
from app.application.services.agent_service.sentiment_node.sentiment_node_configuration import (
    SentimentNodeConfiguration
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.agent.agent_request import AgentRequest
from app.domain.dtos.agent.agent_response import AgentResponse
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)

class AgentService(AgentServiceInterface):
    _KNOWN_EXCEPTIONS = (
        RequestValidationException,
        AgentServiceException,
        UnauthorizedException,
    )

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            authorizer: Authorizer,
            agent_configuration: Optional[AgentConfiguration] = None,
            sentiment_node_configuration: Optional[SentimentNodeConfiguration] = None,
            agent_node_configuration: Optional[AgentNodeConfiguration] = None
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._authorizer = authorizer
        self._agent_configuration = agent_configuration or AgentConfiguration()
        self._sentiment_node_configuration = sentiment_node_configuration or SentimentNodeConfiguration()
        self._agent_node_configuration = agent_node_configuration or AgentNodeConfiguration()

        self._request_validator = AgentRequestValidator(
            agent_configuration=self._agent_configuration
        )

        self._agent_workflow = AgentWorkflow(
            ollama_llm_facade=self._ollama_llm_facade,
            agent_configuration=self._agent_configuration,
            sentiment_node_configuration=self._sentiment_node_configuration,
            agent_node_configuration=self._agent_node_configuration
        )
        self._workflow_built = False
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
            self._request_validator.validate_request(agent_request)

            self._propagate_authorization(None)

            await self._ensure_workflow_built()

            initial_state = self._agent_state_builder.build_agent_state(
                agent_request=agent_request
            )

            final_state = await self._agent_workflow.invoke(initial_state)

            logger.info("Agent execution completed successfully", extra={"user_id": authenticated_user.id})

            return self._build_response(final_state)

        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during agent execution",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise AgentServiceException(
                message=f"Unexpected error executing the agent: {e}",
                status_code=500
            ) from e

    def _propagate_authorization(self, authorization: Optional[str]) -> None:
        tools = self._ollama_llm_facade.tools
        for tool in tools:
            if callable(getattr(tool, "set_authorization", None)):
                tool.set_authorization(authorization)

        if tools:
            logger.debug(
                "Authorization propagated to tools",
                extra={"tool_count": len(tools)}
            )

    async def _ensure_workflow_built(self) -> None:
        if not self._workflow_built:
            await self._agent_workflow.build()
            self._workflow_built = True

    @staticmethod
    def _build_response(final_state: dict) -> AgentResponse:
        messages = final_state.get("messages", [])

        if not messages:
            return AgentResponse(message="")

        last_message = messages[-1]
        if isinstance(last_message, str):
            answer = last_message
        elif hasattr(last_message, "content"):
            answer = str(last_message.content)
        else:
            answer = str(last_message)

        return AgentResponse(message=answer)


# ── FastAPI dependency ────────────────────────────────────────────────────────

async def get_agent_service(request: Request) -> AgentServiceInterface:
    try:
        return request.app.state.agent_service
    except AttributeError:
        logger.error("AgentService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent service is not available",
        )
