from abc import ABC, abstractmethod

from app.application.services.processing.fragment_contextualize_service.interfaces.fragment_contextualize_service_interface import (
    FragmentContextualizeServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.processing.fragment_contextualize.contextualize_fragment_request import (
    ContextualizeFragmentRequest,
)
from app.domain.dtos.processing.fragment_contextualize.contextualize_fragment_response import (
    ContextualizeFragmentResponse,
)


class FragmentContextualizeControllerInterface(ABC):
    @abstractmethod
    async def contextualize_fragment(
            self,
            contextualize_fragment_request: ContextualizeFragmentRequest,
            fragment_contextualize_service: FragmentContextualizeServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> ContextualizeFragmentResponse:
        pass
