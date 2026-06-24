from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser


class ContextualizeFragmentProcessorInterface(ABC):
    @abstractmethod
    async def contextualize_document_fragments(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
    ) -> None:
        pass
