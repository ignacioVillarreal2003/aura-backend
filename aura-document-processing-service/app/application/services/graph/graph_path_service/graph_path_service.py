import logging
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.graph.graph_path_service.interfaces.graph_path_service_interface import (
    GraphPathServiceInterface,
)
from app.configuration.graph.knowledge_graph_settings import KnowledgeGraphSettings
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_field_limits import MAX_PATHS_RETURNED
from app.domain.dtos.graph.graph_path.find_path_request import FindPathRequest
from app.domain.dtos.graph.graph_path.graph_path_response import FindPathResponse
from app.infrastructure.persistence.database.repositories.document_collection_repository.document_collection_repository_interface import (
    DocumentCollectionRepositoryInterface,
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
            document_collection_repository: DocumentCollectionRepositoryInterface,
            authorizer: Authorizer,
            knowledge_graph_settings: Optional[KnowledgeGraphSettings] = None,
    ) -> None:
        self._path_repository = path_repository
        self._document_collection_repository = document_collection_repository
        self._authorizer = authorizer
        self._settings = knowledge_graph_settings or KnowledgeGraphSettings()

    async def find_paths(
            self,
            *,
            request: FindPathRequest,
            authenticated_user: AuthenticatedUser,
            database_session: AsyncSession,
    ) -> FindPathResponse:
        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.GRAPH_PATH}),
        )

        accessible_ids = await self._document_collection_repository.list_all_accessible_document_ids(
            user_id=int(authenticated_user.id),
            database_session=database_session,
            chat_id=None,
            limit=self._settings.accessible_documents_max,
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
