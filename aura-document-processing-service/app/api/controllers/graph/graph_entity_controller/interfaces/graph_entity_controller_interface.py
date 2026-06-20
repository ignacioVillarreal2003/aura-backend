from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.graph.graph_entity_service.interfaces.graph_entity_service_interface import (
    GraphEntityServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.graph.entity_type import EntityType
from app.domain.dtos.graph.graph_entity.graph_entity_with_relations_response import (
    GraphEntityWithRelationsResponse,
)


class GraphEntityControllerInterface(ABC):
    @abstractmethod
    async def get_entity(
            self,
            name: str,
            entity_type: Optional[EntityType],
            depth: int,
            graph_entity_service: GraphEntityServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> GraphEntityWithRelationsResponse:
        pass
