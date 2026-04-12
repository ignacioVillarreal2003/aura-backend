import logging
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI

from app.api.controllers import router
from app.api.handlers.exception_handlers import register_exception_handlers
from app.configuration.cors_configuration import configure_cors
from app.configuration.dependencies import shutdown_dependencies, startup_dependencies
from app.configuration.environment_variables import environment_variables
from app.configuration.logging_configuration import configure_logging
from app.configuration.middlewares.authentication_middleware import add_authentication_middleware
from app.configuration.middlewares.logging_middleware import add_logging_middleware

configure_logging(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application")
    try:
        await startup_dependencies(app=app)
    except Exception:
        logger.critical("Failed to start application")
        raise

    yield

    logger.info("Shutting down application")
    try:
        await shutdown_dependencies(app=app)
        logger.info("Application shut down successfully")
    except Exception:
        logger.error("Error during application shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=environment_variables.app_name,
        version=environment_variables.app_version,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    configure_cors(app)
    _add_middlewares(app)
    _include_routers(app)
    register_exception_handlers(app)

    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app)

    logger.info("FastAPI application configured")
    return app


def _add_middlewares(app: FastAPI) -> None:
    add_logging_middleware(app)
    add_authentication_middleware(app)


def _include_routers(app: FastAPI) -> None:
    app.include_router(router, prefix="/api")


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=environment_variables.app_host,
        port=environment_variables.app_port,
        reload=environment_variables.app_reload,
        log_level=environment_variables.log_level.lower(),
    )
