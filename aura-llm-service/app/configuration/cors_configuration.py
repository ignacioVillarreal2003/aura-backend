from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.configuration.environment_variables import environment_variables


def configure_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=environment_variables.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )
