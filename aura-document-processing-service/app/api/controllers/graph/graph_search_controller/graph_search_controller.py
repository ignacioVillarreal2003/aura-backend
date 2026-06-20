from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.controllers.graph.graph_search_controller.interfaces.graph_search_controller_interface import (
    GraphSearchControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.graph.graph_entity_service.interfaces.graph_entity_service_interface import (
    GraphEntityServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.graph.entity_type import EntityType
from app.domain.dtos.graph.graph_field_limits import MAX_QUERY_RESULTS
from app.domain.dtos.graph.graph_search.graph_search_response import GraphSearchResponse
from app.domain.field_limits import MAX_ENTITY_NAME_CHARS
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session
from app.api.dependencies.services import (
    get_graph_entity_service,
)

_DEFAULT_SEARCH_LIMIT = 10
_MAX_SEARCH_LIMIT = min(50, MAX_QUERY_RESULTS)


class GraphSearchController(GraphSearchControllerInterface):
    async def search(
            self,
            q: str = Query(..., min_length=1, max_length=MAX_ENTITY_NAME_CHARS, description="Prefijo o palabra clave de búsqueda"),
            entity_type: Optional[EntityType] = Query(default=None, alias="type"),
            limit: int = Query(default=_DEFAULT_SEARCH_LIMIT, ge=1, le=_MAX_SEARCH_LIMIT),
            graph_entity_service: GraphEntityServiceInterface = Depends(get_graph_entity_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> GraphSearchResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.GRAPH_SEARCH}),
        )
        results = await graph_entity_service.search_entities(
            query=q,
            entity_type=entity_type,
            limit=limit + 1,
            authenticated_user=authenticated_user,
            database_session=database_session,
        )
        has_more = len(results) > limit
        trimmed = results[:limit]
        return GraphSearchResponse(
            results=trimmed,
            total=len(trimmed),
            has_more=has_more,
        )


router = APIRouter()
graph_search_controller = GraphSearchController()

_error = default_error_responses(
    include_400=True,
    include_403=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Resultados de búsqueda de entidades",
        "model": GraphSearchResponse,
    },
    **_error,
}

router.add_api_route(
    "",
    graph_search_controller.search,
    methods=["GET"],
    response_model=GraphSearchResponse,
    operation_id="searchKnowledgeGraphEntities",
    summary="Buscar entidades por nombre (autocomplete)",
    description=(
        "Búsqueda search-as-you-type sobre entidades del grafo de conocimiento. "
        "Intenta primero prefix match y hace fallback a fulltext si no hay resultados. "
        "Los resultados están siempre filtrados a documentos accesibles por el usuario."
    ),
    responses=_response,
)
