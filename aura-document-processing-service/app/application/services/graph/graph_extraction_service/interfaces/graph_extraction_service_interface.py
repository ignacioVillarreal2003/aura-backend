from abc import ABC, abstractmethod
from typing import Optional

from app.domain.authentication.authenticated_user import AuthenticatedUser


class GraphExtractionServiceInterface(ABC):
    @abstractmethod
    async def extract_for_document(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
            message_id: Optional[str] = None,
    ) -> None:
        pass
