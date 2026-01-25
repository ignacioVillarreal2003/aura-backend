from abc import ABC, abstractmethod

from app.domain.dtos.agent_request import AgentRequest
from app.domain.dtos.agent_response import AgentResponse


class AgentServiceInterface(ABC):
    @abstractmethod
    async def execute_agent(self,
                            request_body: AgentRequest) -> AgentResponse:
        pass
