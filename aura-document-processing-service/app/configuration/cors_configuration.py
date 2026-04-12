from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.configuration.environment_variables import environment_variables


def configure_cors(app: FastAPI) -> None:
    origins = list(environment_variables.cors_origins)
    allow_credentials = not any((o or "").strip() == "*" for o in origins)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"]
    )
