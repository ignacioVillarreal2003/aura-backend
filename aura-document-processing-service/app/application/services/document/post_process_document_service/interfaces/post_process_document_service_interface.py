from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser


class PostProcessDocumentServiceInterface(ABC):
    @abstractmethod
    async def process_document_metadata(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
    ) -> None:
        pass
