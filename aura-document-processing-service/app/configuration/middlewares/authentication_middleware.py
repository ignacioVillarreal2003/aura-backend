from fastapi import FastAPI

from app.infrastructure.http.authentication_provider.authentication_provider_middleware import AuthenticationMiddleware

_EXCLUDED_PATHS = [
    "/",
    "/api/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
]


def add_authentication_middleware(app: FastAPI) -> None:
    app.add_middleware(
        AuthenticationMiddleware,
        excluded_paths=_EXCLUDED_PATHS,
        require_auth=True,
    )
