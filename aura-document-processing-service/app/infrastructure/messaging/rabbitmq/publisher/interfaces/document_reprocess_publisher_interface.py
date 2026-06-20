from abc import ABC, abstractmethod
from typing import Optional

from app.domain.authentication.authenticated_user import AuthenticatedUser


class DocumentReprocessPublisherInterface(ABC):
    @abstractmethod
    async def publish(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
            prefer_docling: bool = False,
            enrich: bool = True,
            graph_extract: bool = True,
            batch_id: Optional[str] = None,
    ) -> str:
        pass
