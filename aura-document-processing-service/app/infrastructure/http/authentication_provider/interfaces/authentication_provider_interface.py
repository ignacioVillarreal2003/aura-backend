from abc import ABC, abstractmethod

from app.infrastructure.http.authentication_provider.dtos.authenticated_user_response import AuthenticatedUserResponse


class AuthenticationProviderInterface(ABC):
    @abstractmethod
    async def validate_token(
            self,
            token: str,
    ) -> AuthenticatedUserResponse:
        pass
