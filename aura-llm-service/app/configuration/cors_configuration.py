import logging
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.configuration.environment_variables import get_settings

logger = logging.getLogger(__name__)


def configure_cors(app: FastAPI) -> None:
    settings = get_settings()
    origins = list(settings.cors_origins)
    has_wildcard = any((o or "").strip() == "*" for o in origins)
    allow_credentials = not has_wildcard

    if has_wildcard:
        if settings.is_production():
            raise ValueError(
                "CORS_ORIGINS contains a wildcard ('*') while ENVIRONMENT is production. "
                "Set CORS_ORIGINS to the explicit frontend origins before deploying."
            )
        logger.warning(
            "CORS is configured with a wildcard origin ('*'). Set CORS_ORIGINS to the "
            "real frontend origins before exposing this service in production."
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
