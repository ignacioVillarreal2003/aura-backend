from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.general.agent.agent_request import AgentRequest
from app.domain.dtos.general.agent.agent_response import AgentResponse


class AgentServiceInterface(ABC):
    @abstractmethod
    async def execute_agent(
            self,
            agent_request: AgentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AgentResponse:
        pass
