import logging
from typing import Optional
from fastapi import APIRouter, Depends, Request

from app.api.controllers.agent_controller.interfaces.agent_controller_interface import AgentControllerInterface
from app.application.services.agent_service.agent_service import get_agent_service
from app.application.services.agent_service.interfaces.agent_service_interface import AgentServiceInterface
from app.domain.dtos.agent.agent_request import AgentRequest
from app.domain.dtos.agent.agent_response import AgentResponse
from app.infrastructure.authentication_provider.authentication_provider import get_current_user
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse

logger = logging.getLogger(__name__)


class AgentController(AgentControllerInterface):
    async def execute_agent(
            self,
            request: Request,
            agent_request: AgentRequest,
            agent_service: AgentServiceInterface = Depends(get_agent_service),
            user: AuthenticationResponse = Depends(get_current_user)
    ) -> AgentResponse:
        logger.info(
            "Execute agent request received",
            extra={"user_id": user.id}
        )

        authorization: Optional[str] = request.headers.get("Authorization")

        agent_response = await agent_service.execute_agent(
            agent_request=agent_request,
            user=user,
            authorization=authorization
        )

        logger.info(
            "Execute agent request completed",
            extra={"user_id": user.id}
        )

        return agent_response


router = APIRouter()

agent_controller = AgentController()

router.post(
    "",
    response_model=AgentResponse,
)(agent_controller.execute_agent)
