from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.graph.graph_entity_service.interfaces.graph_entity_service_interface import (
    GraphEntityServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.graph.entity_type import EntityType
from app.domain.dtos.graph.graph_search.graph_search_response import GraphSearchResponse


class GraphSearchControllerInterface(ABC):
    @abstractmethod
    async def search(
            self,
            q: str,
            entity_type: Optional[EntityType],
            limit: int,
            graph_entity_service: GraphEntityServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> GraphSearchResponse:
        pass
