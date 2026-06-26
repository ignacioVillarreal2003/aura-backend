from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.processing.fragment_contextualize.contextualize_fragment_request import (
    ContextualizeFragmentRequest,
)
from app.domain.dtos.processing.fragment_contextualize.contextualize_fragment_response import (
    ContextualizeFragmentResponse,
)


class FragmentContextualizeServiceInterface(ABC):
    @abstractmethod
    async def contextualize_fragment(
            self,
            contextualize_fragment_request: ContextualizeFragmentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> ContextualizeFragmentResponse:
        pass
