from abc import ABC, abstractmethod
from typing import Optional

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_extraction.graph_extraction_progress import (
    GraphExtractionProgressResponse,
)


class GraphExtractionServiceInterface(ABC):
    @abstractmethod
    async def extract_for_document(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
            force: bool = False,
            message_id: Optional[str] = None,
    ) -> None:
        pass

    @abstractmethod
    async def get_progress(
            self,
            *,
            document_id: int,
    ) -> GraphExtractionProgressResponse:
        pass
