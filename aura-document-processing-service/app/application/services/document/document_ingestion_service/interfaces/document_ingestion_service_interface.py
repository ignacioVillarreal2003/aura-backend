from abc import ABC, abstractmethod
from pathlib import Path

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.persistence.database.orm.document import Document


class DocumentIngestionServiceInterface(ABC):
    @abstractmethod
    async def process_document(
            self,
            document: Document,
            local_file_path: Path,
            user: AuthenticatedUser,
            prefer_docling: bool = False,
            enrich: bool = True,
            graph_extract: bool = True,
    ) -> None:
        pass
