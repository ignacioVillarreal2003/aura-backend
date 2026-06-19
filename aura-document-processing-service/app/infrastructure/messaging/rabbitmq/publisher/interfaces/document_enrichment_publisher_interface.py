from abc import ABC, abstractmethod
from typing import Optional

from app.domain.authentication.authenticated_user import AuthenticatedUser


class DocumentEnrichmentPublisherInterface(ABC):
    @abstractmethod
    async def publish(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
            batch_id: Optional[str] = None,
    ) -> str:
        pass
