from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser


class DocumentPurgePublisherInterface(ABC):
    @abstractmethod
    async def publish(
            self,
            *,
            document_id: int,
            storage_url: str,
            user: AuthenticatedUser,
    ) -> str:
        pass
