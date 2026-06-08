from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.agent.agent_request import AgentRequest
from app.domain.dtos.user_interactions.agent.agent_response import AgentResponse
from app.domain.dtos.user_interactions.agent.agent_stream_events import AgentStreamEvent


class RagAgentServiceInterface(ABC):
    @abstractmethod
    async def execute(
            self,
            agent_request: AgentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AgentResponse:
        pass

    @abstractmethod
    async def execute_stream(
            self,
            agent_request: AgentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[AgentStreamEvent]:
        pass
