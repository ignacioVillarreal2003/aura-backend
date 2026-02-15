import logging

from app.infrastructure.authentication_provider.authentication_provider import (
    AuthenticationProvider
)
from app.infrastructure.authentication_provider.interfaces.authentication_provider_interface import (
    AuthenticationProviderInterface
)
from app.infrastructure.http_client.http_client import HttpClient

logger = logging.getLogger(__name__)


def create_authentication_provider(
        http_client: HttpClient,
        authentication_validate_token_url: str,
        authentication_verify_permissions_url: str,
        authentication_get_user_by_token_url: str,
) -> AuthenticationProviderInterface:
    try:
        logger.info("Creating AuthenticationProvider instance")

        return AuthenticationProvider(
            http_client=http_client,
            authentication_validate_token_url=authentication_validate_token_url,
            authentication_verify_permissions_url=authentication_verify_permissions_url,
            authentication_get_user_by_token_url=authentication_get_user_by_token_url
        )

    except Exception as e:
        logger.exception("Failed to create AuthenticationProvider")
        raise
