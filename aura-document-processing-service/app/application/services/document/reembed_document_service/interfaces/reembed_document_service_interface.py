from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser


class ReembedDocumentServiceInterface(ABC):
    @abstractmethod
    async def reembed_document(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
    ) -> int:
        pass
