from abc import ABC, abstractmethod
from typing import List


class DocumentContextProviderInterface(ABC):
    @abstractmethod
    async def retrieve_context_fragments_by_question(self,
                                                     question: str,
                                                     context_fragments_count: int) -> List[str]:
        pass

    @abstractmethod
    async def retrieve_context_fragments_by_document(self,
                                                     document_id: int) -> List[str]:
        pass
