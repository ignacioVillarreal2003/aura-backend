from abc import ABC, abstractmethod
from typing import List

from app.domain.dtos.fragment.post_process_fragment_controller import (
    PostProcessFragmentStartResponse
)
from app.domain.dtos.fragment.post_process_fragment_controller import (
    PostProcessFragmentStatusResponse
)
from app.infrastructure.http.authentication_provider.dtos.authenticated_user_response import AuthenticationResponse


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
