from abc import ABC, abstractmethod
from typing import List

from app.domain.dtos.post_process_fragment_controller.post_process_fragment_start_response import (
    PostProcessFragmentStartResponse
)
from app.domain.dtos.post_process_fragment_controller.post_process_fragment_status_response import (
    PostProcessFragmentStatusResponse
)
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class PostProcessFragmentServiceInterface(ABC):
    @abstractmethod
    async def start_all(
            self,
            authenticated_user: AuthenticationResponse
    ) -> PostProcessFragmentStartResponse:
        pass

    @abstractmethod
    async def start_for_documents(
            self,
            document_ids: List[int],
            authenticated_user: AuthenticationResponse
    ) -> PostProcessFragmentStartResponse:
        pass

    @abstractmethod
    def get_status(self) -> PostProcessFragmentStatusResponse:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass
