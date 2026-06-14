from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_ontology.graph_ontology_response import GraphOntologyResponse


class GraphOntologyServiceInterface(ABC):
    @abstractmethod
    async def get_ontology(
            self,
            *,
            authenticated_user: AuthenticatedUser,
    ) -> GraphOntologyResponse:
        pass
