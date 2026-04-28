from abc import ABC, abstractmethod

from app.application.services.general.agent_service.interfaces.agent_service_interface import AgentServiceInterface
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.agent.agent_request import AgentRequest
from app.domain.dtos.agent.agent_response import AgentResponse


class AgentControllerInterface(ABC):
    @abstractmethod
    async def execute_agent(
            self,
            agent_request: AgentRequest,
            agent_service: AgentServiceInterface,
            authenticated_user: AuthenticatedUser
    ) -> AgentResponse:
        pass
