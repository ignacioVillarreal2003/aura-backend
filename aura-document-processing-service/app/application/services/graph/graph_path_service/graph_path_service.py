import logging
from typing import Optional
from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.graph.graph_path_service.interfaces.graph_path_service_interface import (
    GraphPathServiceInterface,
)
from app.application.services.graph.knowledge_graph_settings import KnowledgeGraphSettings
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_path.find_path_request import FindPathRequest
from app.domain.dtos.graph.graph_path.graph_path_response import FindPathResponse
from app.infrastructure.http.document_collection_catalog.document_collection_catalog_client_interface import (
    DocumentCollectionCatalogClientInterface,
)
from app.infrastructure.persistence.graph.repositories.graph_path_repository.graph_path_repository_interface import (
    GraphPathRepositoryInterface,
)

logger = logging.getLogger(__name__)


class GraphPathService(GraphPathServiceInterface):
    def __init__(
            self,
            *,
            path_repository: GraphPathRepositoryInterface,
            document_collection_catalog_client: DocumentCollectionCatalogClientInterface,
            knowledge_graph_settings: Optional[KnowledgeGraphSettings] = None,
    ) -> None:
        self._path_repository = path_repository
        self._document_collection_catalog_client = document_collection_catalog_client
        self._settings = knowledge_graph_settings or KnowledgeGraphSettings()

    async def find_paths(
            self,
            *,
            request: FindPathRequest,
            authenticated_user: AuthenticatedUser,
            database_session: AsyncSession,
            authorization_header: str | None = None,
    ) -> FindPathResponse:
        accessible_ids = list(
            await self._document_collection_catalog_client.fetch_all_accessible_document_ids(
                user_id=int(authenticated_user.id),
                authorization_header=authorization_header,
            )
        )
        if not accessible_ids:
            return FindPathResponse(paths=[], truncated=False)

        source_canonical = self._canonicalize(request.source_name)
        target_canonical = self._canonicalize(request.target_name)

        paths = await self._path_repository.find_paths(
            source_canonical_name=source_canonical,
            source_type=request.source_type,
            target_canonical_name=target_canonical,
            target_type=request.target_type,
            max_hops=request.max_hops,
            max_paths=request.max_paths,
            only_shortest=request.only_shortest,
            accessible_document_ids=accessible_ids,
        )

        truncated = len(paths) >= request.max_paths
        return FindPathResponse(paths=paths[: request.max_paths], truncated=truncated)

    @staticmethod
    def _canonicalize(name: str) -> str:
        if not name:
            return ""
        return " ".join(name.strip().lower().split())


async def get_graph_path_service(
        request: Request,
) -> GraphPathServiceInterface:
    service = getattr(request.app.state, "graph_path_service", None)
    if service is None:
        logger.error("GraphPathService is not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge graph path service is not available.",
        )
    return service
