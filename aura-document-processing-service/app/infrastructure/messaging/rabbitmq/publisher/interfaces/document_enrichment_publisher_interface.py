from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser


class DocumentEnrichmentPublisherInterface(ABC):
    @abstractmethod
    async def publish(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
    ) -> str:
        pass
