from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.api.dependencies.rate_limiter import strict_rate_limit
from app.api.controllers.user_interactions.agent_controller.agent_controller_interface import (
    AgentControllerInterface
)
from app.api.openapi.common import default_error_responses
from app.api.sse import sse_response
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.api.dependencies.app_state_services import get_agent_service
from app.application.services.user_interactions.agent_service.interfaces.agent_service_interface import AgentServiceInterface
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.agent.agent_request import AgentRequest
from app.domain.dtos.user_interactions.agent.agent_response import AgentResponse

from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class AgentController(AgentControllerInterface):
    async def execute_agent(
            self,
            agent_request: AgentRequest,
            agent_service: AgentServiceInterface = Depends(get_agent_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> AgentResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_AGENT}),
        )
        return await agent_service.execute_agent(
            agent_request=agent_request,
            authenticated_user=authenticated_user
        )

    async def execute_agent_stream(
            self,
            agent_request: AgentRequest,
            agent_service: AgentServiceInterface = Depends(get_agent_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> StreamingResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_AGENT}),
        )

        return sse_response(
            agent_service.execute_agent_stream(
                agent_request=agent_request,
                authenticated_user=authenticated_user,
            )
        )


router = APIRouter()
agent_controller = AgentController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Respuesta del agente",
        "model": AgentResponse,
    },
    **_error,
}
_response_stream = {
    200: {
        "description": "Stream SSE del agente",
        "content": {"text/event-stream": {}},
    },
    **_error,
}

router.add_api_route(
    "",
    agent_controller.execute_agent,
    methods=["POST"],
    response_model=AgentResponse,
    operation_id="executeAgent",
    summary="Ejecutar agente con herramientas",
    description="Ejecuta el agente con acceso a herramientas de pregunta y resumen sobre documentos.",
    responses=_response,
)

router.add_api_route(
    "/stream",
    agent_controller.execute_agent_stream,
    methods=["POST"],
    response_class=StreamingResponse,
    operation_id="executeAgentStream",
    summary="Ejecutar agente con herramientas (SSE)",
    description=(
        "Server-Sent Events: JSON lines con prefijo `data: `. "
        "Tipos de evento: `progress`, `complete`, `error` (campo discriminador `type`). "
        "Los eventos `progress` indican la etapa actual del pipeline. "
        "El evento `complete` incluye la respuesta completa y los fragmentos utilizados."
    ),
    responses=_response_stream,
)
