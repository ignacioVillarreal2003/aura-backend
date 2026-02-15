from abc import ABC, abstractmethod
from typing import List, Dict

from app.infrastructure.authentication_provider.dtos.authentication_response import (
    AuthenticationResponse
)


class AuthenticationProviderInterface(ABC):
    @abstractmethod
    async def validate_token(
            self,
            token: str
    ) -> AuthenticationResponse:
        pass

    @abstractmethod
    async def verify_permissions(
            self,
            token: str,
            required_roles: List[str]
    ) -> AuthenticationResponse:
        pass

    @abstractmethod
    async def get_user_by_token(
            self,
            token: str
    ) -> AuthenticationResponse:
        pass

    @abstractmethod
    def get_metrics(
            self
    ) -> Dict[str, int]:
        pass
