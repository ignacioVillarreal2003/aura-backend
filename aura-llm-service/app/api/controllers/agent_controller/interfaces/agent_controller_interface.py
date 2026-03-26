from abc import ABC, abstractmethod
from fastapi import Request

from app.application.services.agent_service.interfaces.agent_service_interface import AgentServiceInterface
from app.domain.dtos.agent.agent_request import AgentRequest
from app.domain.dtos.agent.agent_response import AgentResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class AgentControllerInterface(ABC):
    @abstractmethod
    async def execute_agent(
            self,
            request: Request,
            agent_request: AgentRequest,
            agent_service: AgentServiceInterface,
            user: AuthenticationResponse
    ) -> AgentResponse:
        pass
