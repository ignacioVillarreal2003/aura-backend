from abc import ABC, abstractmethod

from app.domain.dtos.fragment.post_process_fragment_controller.post_process_fragments_request import (
    PostProcessFragmentsRequest
)
from app.domain.dtos.fragment.post_process_fragment_controller.post_process_fragments_start_response import (
    PostProcessFragmentsStartResponse
)
from app.domain.dtos.fragment.post_process_fragment_controller.post_process_fragments_status_response import (
    PostProcessFragmentsStatusResponse
)
from app.domain.authentication.authenticated_user import AuthenticatedUser


class PostProcessFragmentServiceInterface(ABC):
    @abstractmethod
    async def start_all(
            self,
            authenticated_user: AuthenticatedUser
    ) -> PostProcessFragmentsStartResponse:
        pass

    @abstractmethod
    async def start_for_documents(
            self,
            post_process_fragments_request: PostProcessFragmentsRequest,
            authenticated_user: AuthenticatedUser
    ) -> PostProcessFragmentsStartResponse:
        pass

    @abstractmethod
    def get_status(
            self
    ) -> PostProcessFragmentsStatusResponse:
        pass

    @abstractmethod
    async def stop(
            self
    ) -> None:
        pass
