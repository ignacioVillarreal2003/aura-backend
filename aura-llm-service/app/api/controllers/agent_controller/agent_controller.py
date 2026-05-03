from fastapi import APIRouter, Depends

from app.api.dependencies.idempotency import optional_idempotency_key
from app.api.dependencies.rate_limiter import strict_rate_limit
from app.api.controllers.agent_controller.agent_controller_interface import (
    AgentControllerInterface
)
from app.api.openapi.common import default_error_responses
from app.application.services.agent_service.agent_service import get_agent_service
from app.application.services.agent_service.interfaces.agent_service_interface import AgentServiceInterface
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.agent.agent_request import AgentRequest
from app.domain.dtos.agent.agent_response import AgentResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class AgentController(AgentControllerInterface):
    async def execute_agent(
            self,
            agent_request: AgentRequest,
            agent_service: AgentServiceInterface = Depends(get_agent_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _idemp: None = Depends(optional_idempotency_key),
            _rl: None = Depends(strict_rate_limit),
    ) -> AgentResponse:
        return await agent_service.execute_agent(
            agent_request=agent_request,
            authenticated_user=authenticated_user
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
