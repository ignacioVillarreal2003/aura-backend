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
            post_process: bool = True,
            post_process_graph: bool = True,
    ) -> None:
        """Reprocess a document end-to-end from its stored object.

        Soft-deletes the existing fragments and re-runs the full ingestion pipeline
        (re-download, re-chunk, re-embed) against the object already in storage.
        """
        ...
