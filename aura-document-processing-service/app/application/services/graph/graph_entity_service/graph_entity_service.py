import logging
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.graph.graph_entity_service.exceptions.graph_entity_service_exception import (
    GraphEntityNotFoundException,
)
from app.application.services.graph.graph_entity_service.interfaces.graph_entity_service_interface import (
    GraphEntityServiceInterface,
)
from app.configuration.graph.knowledge_graph_settings import KnowledgeGraphSettings
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.graph.entity_type import EntityType
from app.domain.dtos.graph.graph_entity.graph_entity_with_relations_response import (
    GraphEntityWithRelationsResponse,
)
from app.infrastructure.http.document_collection_catalog.document_collection_catalog_client_interface import (
    DocumentCollectionCatalogClientInterface,
)
from app.infrastructure.persistence.database.repositories.document_collection_repository.document_collection_repository_interface import (
    DocumentCollectionRepositoryInterface,
)
from app.infrastructure.persistence.graph.repositories.graph_entity_repository.graph_entity_repository_interface import (
    GraphEntityRepositoryInterface,
)
from app.infrastructure.persistence.graph.repositories.graph_relation_repository.graph_relation_repository_interface import (
    GraphRelationRepositoryInterface,
)

logger = logging.getLogger(__name__)


class GraphEntityService(GraphEntityServiceInterface):
    def __init__(
            self,
            *,
            entity_repository: GraphEntityRepositoryInterface,
            relation_repository: GraphRelationRepositoryInterface,
            document_collection_repository: DocumentCollectionRepositoryInterface,
            document_collection_catalog_client: DocumentCollectionCatalogClientInterface,
            authorizer: Authorizer,
            knowledge_graph_settings: Optional[KnowledgeGraphSettings] = None,
    ) -> None:
        self._entity_repository = entity_repository
        self._relation_repository = relation_repository
        self._document_collection_repository = document_collection_repository
        self._document_collection_catalog_client = document_collection_catalog_client
        self._authorizer = authorizer
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
        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.GRAPH_ENTITY}),
        )

        canonical = self._canonicalize(name)
        if not canonical:
            raise GraphEntityNotFoundException("The entity name is required.")

        collection_ids = await self._document_collection_catalog_client.fetch_all_accessible_collection_ids(
            user_id=int(authenticated_user.id),
            authorization_header=authorization_header,
        )
        accessible_ids = await self._document_collection_repository.list_all_accessible_document_ids(
            user_id=int(authenticated_user.id),
            database_session=database_session,
            accessible_collection_ids=collection_ids,
            chat_id=None,
            limit=self._settings.accessible_documents_max,
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

    @staticmethod
    def _canonicalize(name: str) -> str:
        if not name:
            return ""
        return " ".join(name.strip().lower().split())


async def get_graph_entity_service(
        request: Request,
) -> GraphEntityServiceInterface:
    service = getattr(request.app.state, "graph_entity_service", None)
    if service is None:
        logger.error("GraphEntityService is not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge graph entity service is not available.",
        )
    return service
