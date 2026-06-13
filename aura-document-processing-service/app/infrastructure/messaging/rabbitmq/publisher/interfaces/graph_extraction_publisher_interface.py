from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser


class GraphExtractionPublisherInterface(ABC):
    @abstractmethod
    async def publish(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
            force: bool = False,
    ) -> str:
        pass
