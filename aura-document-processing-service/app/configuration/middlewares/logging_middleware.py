import logging
from fastapi import FastAPI, Request

logger = logging.getLogger(__name__)


def add_logging_middleware(
        app: FastAPI
) -> None:
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        logger.info("Request: %s %s", request.method, request.url.path)
        response = await call_next(request)
        logger.info("Response: %s", response.status_code)
        return response
