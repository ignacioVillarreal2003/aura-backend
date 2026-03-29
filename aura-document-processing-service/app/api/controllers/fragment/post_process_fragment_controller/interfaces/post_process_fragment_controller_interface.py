from abc import ABC, abstractmethod

from app.application.services.fragment.post_process_fragment_service.interfaces.post_process_fragment_service_interface import (
    PostProcessFragmentServiceInterface
)
from app.domain.dtos.fragment.post_process_fragment_controller.post_process_fragment_start_response import (
    PostProcessFragmentStartResponse
)
from app.domain.dtos.fragment.post_process_fragment_controller.post_process_fragment_status_response import (
    PostProcessFragmentStatusResponse
)
from app.domain.dtos.fragment.post_process_fragment_controller.post_process_fragments_request import (
    PostProcessFragmentsRequest
)
from app.domain.models.authenticated_user import AuthenticatedUser


class PostProcessFragmentControllerInterface(ABC):
    @abstractmethod
    async def start_all(
            self,
            post_process_fragment_service: PostProcessFragmentServiceInterface,
            authenticated_user: AuthenticatedUser
    ) -> PostProcessFragmentStartResponse:
        pass

    @abstractmethod
    async def start_for_documents(
            self,
            post_process_fragments_request: PostProcessFragmentsRequest,
            post_process_fragment_service: PostProcessFragmentServiceInterface,
            authenticated_user: AuthenticatedUser
    ) -> PostProcessFragmentStartResponse:
        pass

    @abstractmethod
    async def get_status(
            self,
            post_process_fragment_service: PostProcessFragmentServiceInterface,
            authenticated_user: AuthenticatedUser
    ) -> PostProcessFragmentStatusResponse:
        pass

    @abstractmethod
    async def stop(
            self,
            post_process_fragment_service: PostProcessFragmentServiceInterface,
            authenticated_user: AuthenticatedUser
    ) -> None:
        pass
