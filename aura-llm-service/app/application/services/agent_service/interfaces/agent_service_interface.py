from abc import ABC, abstractmethod
from typing import Optional

from app.domain.dtos.agent.agent_request import AgentRequest
from app.domain.dtos.agent.agent_response import AgentResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class AgentServiceInterface(ABC):
    @abstractmethod
    async def execute_agent(
            self,
            agent_request: AgentRequest,
            user: AuthenticationResponse,
            authorization: Optional[str] = None
    ) -> AgentResponse:
        pass
