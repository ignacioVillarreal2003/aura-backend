from abc import ABC, abstractmethod

from app.domain.dtos.document.reembed.reembed_request import ReembedRequest
from app.domain.dtos.document.reembed.reembed_response import ReembedResponse


class DocumentReembedControllerInterface(ABC):
    @abstractmethod
    async def reembed(
            self,
            request: ReembedRequest,
    ) -> ReembedResponse:
        pass
