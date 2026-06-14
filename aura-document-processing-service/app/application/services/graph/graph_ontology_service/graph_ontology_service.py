import logging
from typing import Optional

from app.application.services.graph.graph_ontology_service.interfaces.graph_ontology_service_interface import (
    GraphOntologyServiceInterface,
)
from app.application.services.graph.knowledge_graph_settings import KnowledgeGraphSettings
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_ontology.graph_ontology_response import GraphOntologyResponse

logger = logging.getLogger(__name__)


class GraphOntologyService(GraphOntologyServiceInterface):
    def __init__(
            self,
            *,
            knowledge_graph_settings: Optional[KnowledgeGraphSettings] = None,
    ) -> None:
        self._settings = knowledge_graph_settings or KnowledgeGraphSettings()

    async def get_ontology(
            self,
            *,
            authenticated_user: AuthenticatedUser,
    ) -> GraphOntologyResponse:
        return GraphOntologyResponse(
            entity_types=self._settings.resolve_allowed_entity_types(),
            relation_types=self._settings.resolve_allowed_relation_types(),
            query_max_results=self._settings.query_max_results,
            query_max_depth=self._settings.query_max_neighbor_depth,
        )
