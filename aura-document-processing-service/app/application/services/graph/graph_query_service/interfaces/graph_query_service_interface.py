from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_query.graph_query_request import GraphQueryRequest
from app.domain.dtos.graph.graph_query.graph_query_response import GraphQueryResponse


class GraphQueryServiceInterface(ABC):
    @abstractmethod
    async def execute(
            self,
            *,
            request: GraphQueryRequest,
            authenticated_user: AuthenticatedUser,
            database_session: AsyncSession,
            authorization_header: Optional[str] = None,
    ) -> GraphQueryResponse:
        pass
