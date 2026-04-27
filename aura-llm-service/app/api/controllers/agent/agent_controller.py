import logging

from fastapi import APIRouter, Depends

from app.api.dependencies.idempotency import optional_idempotency_key
from app.api.dependencies.rate_limiter import strict_rate_limit
from app.api.controllers.agent.agent_controller_interface import (
    AgentControllerInterface
)
from app.api.openapi.common import default_error_responses
from app.application.services.general.agent_service.agent_service import get_agent_service
from app.application.services.general.agent_service.interfaces.agent_service_interface import AgentServiceInterface
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.general.agent.agent_request import AgentRequest
from app.domain.dtos.general.agent.agent_response import AgentResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)


class AgentController(AgentControllerInterface):
    async def execute_agent(
            self,
            agent_request: AgentRequest,
            agent_service: AgentServiceInterface = Depends(get_agent_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _idemp: None = Depends(optional_idempotency_key),
            _rl: None = Depends(strict_rate_limit),
    ) -> AgentResponse:
        logger.info(
            "Handling execute agent request",
            extra={
                "user_id": authenticated_user.id
            }
        )

        agent_response = await agent_service.execute_agent(
            agent_request=agent_request,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Execute agent completed successfully",
            extra={
                "user_id": authenticated_user.id
            }
        )

        return agent_response


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
