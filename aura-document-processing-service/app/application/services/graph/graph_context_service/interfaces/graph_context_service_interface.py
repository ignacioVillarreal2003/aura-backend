from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_context.graph_context_request import GraphContextRequest
from app.domain.dtos.graph.graph_context.graph_context_response import GraphContextResponse


class GraphContextServiceInterface(ABC):
    @abstractmethod
    async def get_context(
            self,
            *,
            request: GraphContextRequest,
            authenticated_user: AuthenticatedUser,
            database_session: AsyncSession,
            authorization_header: str | None = None,
    ) -> GraphContextResponse:
        pass
