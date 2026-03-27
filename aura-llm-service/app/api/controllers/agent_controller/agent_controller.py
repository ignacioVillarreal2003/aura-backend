import logging
from typing import Optional
from fastapi import APIRouter, Depends, Request

from app.api.controllers.controller_logging import log_controller
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
        log_controller(
            logger,
            operation="execute_agent",
            phase="start",
            user_id=user.id,
            message_count=len(agent_request.messages),
        )

        authorization: Optional[str] = request.headers.get("Authorization")

        agent_response = await agent_service.execute_agent(
            agent_request=agent_request,
            user=user,
            authorization=authorization
        )

        log_controller(
            logger,
            operation="execute_agent",
            phase="success",
            user_id=user.id,
            response_length=len(agent_response.message or ""),
        )

        return agent_response


router = APIRouter()

agent_controller = AgentController()

router.post(
    "",
    response_model=AgentResponse,
)(agent_controller.execute_agent)
