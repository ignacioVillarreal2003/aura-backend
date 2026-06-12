from abc import ABC, abstractmethod
from starlette.responses import StreamingResponse

from app.application.services.user_interactions.rag_agent_service.interfaces.rag_agent_service_interface import (
    RagAgentServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.agent.agent_request import AgentRequest
from app.domain.dtos.user_interactions.agent.agent_response import AgentResponse


class RagAgentControllerInterface(ABC):
    @abstractmethod
    async def execute(
            self,
            agent_request: AgentRequest,
            rag_agent_service: RagAgentServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> AgentResponse:
        pass

    @abstractmethod
    async def execute_stream(
            self,
            agent_request: AgentRequest,
            rag_agent_service: RagAgentServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> StreamingResponse:
        pass
