import logging
from fastapi import HTTPException, Request, status

from app.infrastructure.http_client.http_client import HttpClient

logger = logging.getLogger(__name__)


async def get_http_client(
        request: Request
) -> HttpClient:
    try:
        http_client: HttpClient = request.app.state.http_client

        if not http_client.is_started:
            logger.error("HttpClient found but not started")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="HTTP client not available",
            )

        return http_client

    except AttributeError:
        logger.error("HttpClient not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="HTTP client not configured",
        )
