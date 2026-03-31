from abc import ABC, abstractmethod
from typing import Optional
from fastapi import Request

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.dtos.authenticated_user_response import AuthenticatedUserResponse


class AuthenticationProviderInterface(ABC):
    @abstractmethod
    async def validate_token(self, token: str) -> AuthenticatedUserResponse:
        pass

    @abstractmethod
    def evaluate_service_auth(self, request: Request) -> Optional[AuthenticatedUser]:
        pass