from abc import ABC, abstractmethod

from app.domain.dtos.document.reprocess.reprocess_request import ReprocessRequest
from app.domain.dtos.document.reprocess.reprocess_response import ReprocessResponse


class DocumentReprocessControllerInterface(ABC):
    @abstractmethod
    async def reprocess(
            self,
            request: ReprocessRequest,
    ) -> ReprocessResponse:
        pass
