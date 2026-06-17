from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser


class ReembedDocumentServiceInterface(ABC):
    @abstractmethod
    async def reembed_document(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
            force: bool = False,
    ) -> int:
        """Re-embed a document's existing fragments with the active model.

        Returns the number of fragments that were re-embedded.
        """
        ...
