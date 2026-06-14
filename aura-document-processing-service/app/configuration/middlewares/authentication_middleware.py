from fastapi import FastAPI

from app.infrastructure.http.authentication_provider.authentication_provider_middleware import (
    AuthenticationProviderMiddleware,
)

_EXCLUDED_PATHS = [
    "/",
    "/api/v1/health",
    "/api/v1/ready",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/metrics"
]


def add_authentication_middleware(app: FastAPI) -> None:
    app.add_middleware(
        AuthenticationProviderMiddleware,
        excluded_paths=_EXCLUDED_PATHS,
    )
