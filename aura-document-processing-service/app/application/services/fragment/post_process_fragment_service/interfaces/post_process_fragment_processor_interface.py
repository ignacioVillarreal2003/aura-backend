from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser


class PostProcessFragmentProcessorInterface(ABC):
    @abstractmethod
    async def process_document_fragments(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
    ) -> None:
        pass
