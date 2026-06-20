from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.graph.graph_context_service.interfaces.graph_context_service_interface import (
    GraphContextServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_context.graph_context_request import GraphContextRequest
from app.domain.dtos.graph.graph_context.graph_context_response import GraphContextResponse


class GraphContextControllerInterface(ABC):
    @abstractmethod
    async def get_context(
            self,
            graph_context_request: GraphContextRequest,
            graph_context_service: GraphContextServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> GraphContextResponse:
        pass
