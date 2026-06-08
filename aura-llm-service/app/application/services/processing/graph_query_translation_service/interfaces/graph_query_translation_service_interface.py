from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.processing.graph_query_translation.translate_graph_query_request import (
    TranslateGraphQueryRequest,
)
from app.domain.dtos.processing.graph_query_translation.translate_graph_query_response import (
    TranslateGraphQueryResponse,
)


class GraphQueryTranslationServiceInterface(ABC):
    @abstractmethod
    async def translate_graph_query(
            self,
            translate_graph_query_request: TranslateGraphQueryRequest,
            authenticated_user: AuthenticatedUser,
    ) -> TranslateGraphQueryResponse:
        pass
