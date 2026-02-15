import logging
from typing import Optional

from app.infrastructure.http_client.http_client import HttpClient
from app.infrastructure.http_client.http_client_settings import HttpClientSettings
from app.infrastructure.http_client.interfaces.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)


def create_http_client(
        http_client_settings: Optional[HttpClientSettings] = None,
        **config_kwargs
) -> HttpClientInterface:
    try:
        logger.info("Creating HttpClient instance")

        if http_client_settings is None:
            http_client_settings = HttpClientSettings(
                **config_kwargs
            )

        return HttpClient(
            http_client_settings=http_client_settings
        )

    except Exception as e:
        logger.exception("Failed to create HttpClient")
        raise
