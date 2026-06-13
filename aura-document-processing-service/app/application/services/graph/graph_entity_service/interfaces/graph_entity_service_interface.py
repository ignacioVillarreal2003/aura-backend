from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.graph.entity_type import EntityType
from app.domain.dtos.graph.graph_entity.graph_entity_response import GraphEntityResponse
from app.domain.dtos.graph.graph_entity.graph_entity_with_relations_response import (
    GraphEntityWithRelationsResponse,
)


class GraphEntityServiceInterface(ABC):
    @abstractmethod
    async def get_entity_with_relations(
            self,
            *,
            name: str,
            entity_type: Optional[EntityType],
            depth: int,
            authenticated_user: AuthenticatedUser,
            database_session: AsyncSession,
            authorization_header: Optional[str] = None,
    ) -> GraphEntityWithRelationsResponse:
        pass

    @abstractmethod
    async def search_entities(
            self,
            *,
            query: str,
            entity_type: Optional[EntityType],
            limit: int,
            authenticated_user: AuthenticatedUser,
            database_session: AsyncSession,
            authorization_header: Optional[str] = None,
    ) -> list[GraphEntityResponse]:
        pass
