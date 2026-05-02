from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.graph.hybrid_retrieval_orchestrator.interfaces.hybrid_retrieval_orchestrator_interface import (
    HybridRetrievalOrchestratorInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_query.graph_hybrid_query_response import (
    GraphHybridQueryResponse,
)
from app.domain.dtos.graph.graph_query.graph_query_request import GraphQueryRequest


class GraphHybridQueryControllerInterface(ABC):
    @abstractmethod
    async def hybrid_query(
            self,
            graph_query_request: GraphQueryRequest,
            hybrid_retrieval_orchestrator: HybridRetrievalOrchestratorInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> GraphHybridQueryResponse:
        pass
