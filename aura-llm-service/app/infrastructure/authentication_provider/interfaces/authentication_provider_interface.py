from abc import ABC, abstractmethod

from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class AuthenticationProviderInterface(ABC):
    @abstractmethod
    async def validate_token(self, token: str) -> AuthenticationResponse:
        pass
