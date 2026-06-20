from typing import Optional
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.controllers.graph.graph_entity_controller.interfaces.graph_entity_controller_interface import (
    GraphEntityControllerInterface,
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
from app.domain.dtos.graph.graph_entity.graph_entity_with_relations_response import (
    GraphEntityWithRelationsResponse,
)
from app.domain.field_limits import MAX_ENTITY_NAME_CHARS, MAX_PATH_HOPS
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session
from app.api.dependencies.services import (
    get_graph_entity_service,
)


class GraphEntityController(GraphEntityControllerInterface):
    async def get_entity(
            self,
            name: str = Path(..., min_length=1, max_length=MAX_ENTITY_NAME_CHARS),
            entity_type: Optional[EntityType] = Query(default=None, alias="type"),
            depth: int = Query(default=1, ge=1, le=MAX_PATH_HOPS),
            graph_entity_service: GraphEntityServiceInterface = Depends(
                get_graph_entity_service
            ),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> GraphEntityWithRelationsResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.GRAPH_ENTITY}),
        )

        return await graph_entity_service.get_entity_with_relations(
            name=name,
            entity_type=entity_type,
            depth=depth,
            authenticated_user=authenticated_user,
            database_session=database_session,
        )


router = APIRouter()
graph_entity_controller = GraphEntityController()

_error = default_error_responses(
    include_400=True,
    include_403=True,
    include_404=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Entidad y sus relaciones",
        "model": GraphEntityWithRelationsResponse,
    },
    **_error,
}

router.add_api_route(
    "/{name}",
    graph_entity_controller.get_entity,
    methods=["GET"],
    response_model=GraphEntityWithRelationsResponse,
    operation_id="getKnowledgeGraphEntity",
    summary="Obtener entidad por nombre",
    description=(
        "Devuelve una entidad por su nombre canónico junto con sus relaciones "
        "directas hasta la profundidad indicada."
    ),
    responses=_response,
)
