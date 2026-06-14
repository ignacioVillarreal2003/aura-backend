from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser


class DocumentEnrichmentServiceInterface(ABC):
    @abstractmethod
    async def enrich_for_document(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
    ) -> None:
        pass
