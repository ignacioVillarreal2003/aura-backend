from abc import ABC, abstractmethod
from typing import Optional

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.graph_context_provider.dtos.graph_context_dtos import (
    GraphContextResult,
    GraphQueryResult,
)


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
        pass

    @abstractmethod
    async def execute_graph_query(
            self,
            *,
            authenticated_user: AuthenticatedUser,
            question: str,
            max_results: int = 20,
            chat_id: Optional[int] = None,
    ) -> GraphQueryResult:
        pass
