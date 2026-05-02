from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_query.graph_hybrid_query_response import (
    GraphHybridQueryResponse,
)
from app.domain.dtos.graph.graph_query.graph_query_request import GraphQueryRequest


class HybridRetrievalOrchestratorInterface(ABC):
    @abstractmethod
    async def retrieve(
            self,
            *,
            request: GraphQueryRequest,
            authenticated_user: AuthenticatedUser,
            database_session: AsyncSession,
    ) -> GraphHybridQueryResponse:
        pass
