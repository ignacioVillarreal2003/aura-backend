from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.graph.graph_query_service.interfaces.graph_query_service_interface import (
    GraphQueryServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_query.graph_query_request import GraphQueryRequest
from app.domain.dtos.graph.graph_query.graph_query_response import GraphQueryResponse


class GraphQueryControllerInterface(ABC):
    @abstractmethod
    async def query(
            self,
            graph_query_request: GraphQueryRequest,
            graph_query_service: GraphQueryServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> GraphQueryResponse:
        pass
