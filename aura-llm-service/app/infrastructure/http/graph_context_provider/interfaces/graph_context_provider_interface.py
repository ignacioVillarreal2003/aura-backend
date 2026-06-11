from abc import ABC, abstractmethod
from typing import Optional

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.graph_context_provider.dtos.graph_context_dtos import GraphContextResult


class GraphContextProviderInterface(ABC):
    @property
    @abstractmethod
    def is_active(self) -> bool:
        pass

    @abstractmethod
    async def retrieve_graph_context(
            self,
            *,
            authenticated_user: AuthenticatedUser,
            question: Optional[str],
            terms: list[str],
            chat_id: Optional[int] = None,
            max_entities: int = 8,
            max_relations: int = 30,
    ) -> GraphContextResult:
        """Fetch compact graph facts for the question/terms.

        Implementations must be failure-tolerant: any transport or parsing
        error returns an empty result instead of raising, so the RAG flow
        never breaks because of the knowledge graph."""
        pass
