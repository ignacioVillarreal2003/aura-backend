from abc import ABC, abstractmethod
from typing import Optional


class DocumentContextProviderInterface(ABC):
    @abstractmethod
    async def retrieve_context_fragments_by_question(
            self,
            question: str,
            max_context_fragments: int,
            authorization: Optional[str] = None
    ) -> list[str]:
        pass

    @abstractmethod
    async def retrieve_context_fragments_by_document(
            self,
            document_id: int,
            authorization: Optional[str] = None
    ) -> list[str]:
        pass
