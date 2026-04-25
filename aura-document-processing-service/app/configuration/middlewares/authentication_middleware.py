from fastapi import FastAPI

from app.infrastructure.http.authentication_provider.authentication_provider_middleware import (
    AuthenticationProviderMiddleware
)

_EXCLUDED_PATHS = [
    "/",
    "/api/health",
    "/api/v1/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/api/v1/create-document/internal",
    "/metrics"
]


def add_authentication_middleware(
        app: FastAPI
) -> None:
    app.add_middleware(
        AuthenticationProviderMiddleware,
        excluded_paths=_EXCLUDED_PATHS
    )
