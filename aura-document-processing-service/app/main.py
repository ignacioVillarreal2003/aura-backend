import logging
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.api.exception_handlers.exception_handlers import register_exception_handlers
from app.configuration.dependencies import (
    startup_dependencies,
    shutdown_dependencies
)
from app.configuration.logging_configuration import configure_logging
from app.configuration.environment_variables import environment_variables

configure_logging(
    level=logging.INFO
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("Starting FastAPI Application")
    logger.info("=" * 60)

    try:
        await startup_dependencies()
        logger.info("Application started successfully")

    except Exception:
        logger.critical("Failed to start application")
        raise

    yield

    logger.info("=" * 60)
    logger.info("Shutting down FastAPI Application")
    logger.info("=" * 60)

    try:
        await shutdown_dependencies()
        logger.info("Application shut down successfully")

    except Exception:
        logger.error("Error during application shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=environment_variables.app_name,
        version=environment_variables.app_version,
        description="Agent-based document question answering",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json"
    )

    configure_cors(app)
    add_middleware(app)
    include_routers(app)
    register_exception_handlers(app)

    logger.info("FastAPI application configured")

    return app


def configure_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=environment_variables.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    logger.debug("CORS configured")


def add_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def log_requests(request: Request,
                           call_next):
        logger.info(f"Request: {request.method} {request.url.path}")

        response = await call_next(request)

        logger.info(f"Response: {response.status_code}")

        return response

    logger.debug("Middleware added")


def include_routers(app: FastAPI) -> None:
    app.include_router(
        router,
        prefix="/api"
    )

    logger.debug("Routers included")


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=environment_variables.app_host,
        port=environment_variables.app_port,
        reload=environment_variables.app_reload,
        log_level=environment_variables.log_level.lower()
    )
