from abc import ABC, abstractmethod

from app.application.services.graph.graph_ontology_service.interfaces.graph_ontology_service_interface import (
    GraphOntologyServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_ontology.graph_ontology_response import GraphOntologyResponse


class GraphOntologyControllerInterface(ABC):
    @abstractmethod
    async def get_ontology(
            self,
            graph_ontology_service: GraphOntologyServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> GraphOntologyResponse:
        pass
