import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.graph.graph_entity_service.exceptions.graph_entity_service_exception import (
    GraphEntityNotFoundException,
)
from app.application.services.graph.graph_entity_service.interfaces.graph_entity_service_interface import (
    GraphEntityServiceInterface,
)
from app.application.services.graph.knowledge_graph_settings import KnowledgeGraphSettings
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.graph.entity_type import EntityType
from app.domain.dtos.graph.graph_entity.graph_entity_response import GraphEntityResponse
from app.domain.dtos.graph.graph_entity.graph_entity_with_relations_response import (
    GraphEntityWithRelationsResponse,
)
from app.infrastructure.http.authentication_provider.request_token import get_request_token
from app.infrastructure.http.document_collection_catalog.interfaces.document_collection_catalog_client_interface import (
    DocumentCollectionCatalogClientInterface,
)
from app.infrastructure.persistence.graph.repositories.interfaces.graph_entity_repository_interface import (
    GraphEntityRepositoryInterface,
)
from app.infrastructure.persistence.graph.repositories.interfaces.graph_relation_repository_interface import (
    GraphRelationRepositoryInterface,
)

logger = logging.getLogger(__name__)


class GraphEntityService(GraphEntityServiceInterface):
    def __init__(
            self,
            *,
            entity_repository: GraphEntityRepositoryInterface,
            relation_repository: GraphRelationRepositoryInterface,
            document_collection_catalog_client: DocumentCollectionCatalogClientInterface,
            knowledge_graph_settings: Optional[KnowledgeGraphSettings] = None,
    ) -> None:
        self._entity_repository = entity_repository
        self._relation_repository = relation_repository
        self._document_collection_catalog_client = document_collection_catalog_client
        self._settings = knowledge_graph_settings or KnowledgeGraphSettings()

    async def get_entity_with_relations(
            self,
            *,
            name: str,
            entity_type: Optional[EntityType],
            depth: int,
            authenticated_user: AuthenticatedUser,
            database_session: AsyncSession,
            authorization_header: str | None = None,
    ) -> GraphEntityWithRelationsResponse:
        canonical = self._canonicalize(name)
        if not canonical:
            raise GraphEntityNotFoundException("The entity name is required.")

        token = authorization_header or get_request_token()
        accessible_ids = list(
            await self._document_collection_catalog_client.fetch_all_accessible_document_ids(
                user_id=int(authenticated_user.id),
                authorization_header=token,
            )
        )
        if not accessible_ids:
            raise GraphEntityNotFoundException(
                "The entity could not be found in any accessible document."
            )

        entity = await self._entity_repository.find_by_name(
            canonical_name=canonical,
            entity_type=entity_type,
            accessible_document_ids=accessible_ids,
        )
        if entity is None:
            raise GraphEntityNotFoundException("The entity was not found.")

        clamped_depth = max(1, min(int(depth), self._settings.query_max_neighbor_depth))
        relations = await self._relation_repository.list_neighbors_of(
            canonical_name=canonical,
            entity_type=entity_type,
            depth=clamped_depth,
            relation_types=None,
            accessible_document_ids=accessible_ids,
            limit=self._settings.query_max_results,
        )

        return GraphEntityWithRelationsResponse(
            entity=entity,
            relations=relations,
        )

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
        canonical_query = self._canonicalize(query)
        if not canonical_query:
            return []

        clamped_limit = max(1, min(limit, self._settings.query_max_results))

        token = authorization_header or get_request_token()
        accessible_ids = list(
            await self._document_collection_catalog_client.fetch_all_accessible_document_ids(
                user_id=int(authenticated_user.id),
                authorization_header=token,
            )
        )
        if not accessible_ids:
            return []

        results = await self._entity_repository.search_by_name_prefix(
            canonical_prefix=canonical_query,
            entity_type=entity_type,
            accessible_document_ids=accessible_ids,
            limit=clamped_limit,
        )

        if not results:
            results = await self._entity_repository.fulltext_search(
                query_string=canonical_query,
                entity_type=entity_type,
                accessible_document_ids=accessible_ids,
                limit=clamped_limit,
            )

        return results

    @staticmethod
    def _canonicalize(name: str) -> str:
        if not name:
            return ""
        return " ".join(name.strip().lower().split())
