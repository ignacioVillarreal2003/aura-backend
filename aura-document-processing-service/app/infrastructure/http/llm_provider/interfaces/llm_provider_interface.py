from abc import ABC, abstractmethod
from typing import Optional

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.llm_provider.dtos.classify_document_response import ClassifyDocumentResponse
from app.infrastructure.http.llm_provider.dtos.contextualize_fragment_response import (
    ContextualizeFragmentResponse,
)
from app.infrastructure.http.llm_provider.dtos.extract_entities_relations_response import (
    ExtractEntitiesRelationsResponse,
)
from app.infrastructure.http.llm_provider.dtos.translate_graph_query_request import GraphOntology
from app.infrastructure.http.llm_provider.dtos.translate_graph_query_response import (
    TranslateGraphQueryResponse,
)


class LlmProviderInterface(ABC):
    @abstractmethod
    async def classify_document(
            self,
            document_name: str,
            content: str,
            authenticated_user: AuthenticatedUser,
    ) -> ClassifyDocumentResponse:
        pass

    @abstractmethod
    async def contextualize_fragment(
            self,
            document_summary: str,
            content: str,
            authenticated_user: AuthenticatedUser,
    ) -> ContextualizeFragmentResponse:
        pass

    @abstractmethod
    async def extract_entities_relations(
            self,
            content: str,
            document_id: int,
            fragment_id: int,
            allowed_entity_types: list[str],
            allowed_relation_types: Optional[list[str]],
            authenticated_user: AuthenticatedUser,
    ) -> ExtractEntitiesRelationsResponse:
        pass

    @abstractmethod
    async def translate_graph_query(
            self,
            question: str,
            ontology: GraphOntology,
            authenticated_user: AuthenticatedUser,
    ) -> TranslateGraphQueryResponse:
        pass
