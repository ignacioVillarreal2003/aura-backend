import logging
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.configuration.environment_variables import environment_variables

logger = logging.getLogger(__name__)


def configure_cors(app: FastAPI) -> None:
    origins = list(environment_variables.cors_origins)
    allow_credentials = not any((o or "").strip() == "*" for o in origins)

    if not allow_credentials:
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
