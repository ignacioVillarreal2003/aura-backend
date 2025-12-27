from abc import ABC, abstractmethod
from typing import Sequence


class ContextProviderInterface(ABC):
    @abstractmethod
    async def retrieve_fragments_by_question(self,
                                             question: str,
                                             max_fragments: int) -> Sequence[str]:
        pass

    @abstractmethod
    async def retrieve_fragments_by_document(self,
                                             document_id: int) -> Sequence[str]:
        pass
