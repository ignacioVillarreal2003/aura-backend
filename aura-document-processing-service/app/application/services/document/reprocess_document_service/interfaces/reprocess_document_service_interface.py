from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser


class ReprocessDocumentServiceInterface(ABC):
    @abstractmethod
    async def reprocess_document(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
            prefer_docling: bool = False,
            enrich: bool = True,
            graph_extract: bool = True,
    ) -> None:
        pass