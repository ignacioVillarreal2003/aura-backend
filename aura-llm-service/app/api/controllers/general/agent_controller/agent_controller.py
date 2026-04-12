import logging
from fastapi import APIRouter, Depends

from app.api.controllers.general.agent_controller.interfaces.agent_controller_interface import (
    AgentControllerInterface
)
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
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
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

router.post(
    "",
    response_model=AgentResponse,
)(agent_controller.execute_agent)
