import logging
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.controllers import router
from app.api.openapi.descriptions import openapi_tags_metadata, root_api_description
from app.api.openapi.swagger_bearer import install_openapi_bearer
from app.api.handlers.exception_handlers import register_exception_handlers
from app.configuration.cors_configuration import configure_cors
from app.configuration.dependencies import shutdown_dependencies, startup_dependencies
from app.configuration.environment_variables import environment_variables
from app.configuration.gpu_guard import verify_gpu_availability
from app.configuration.logging_configuration import configure_logging
from app.configuration.middlewares.authentication_middleware import add_authentication_middleware
from app.configuration.middlewares.logging_middleware import add_logging_middleware
from app.configuration.production_invariants import assert_production_invariants

_root_log_level = getattr(
    logging,
    environment_variables.log_level,
    logging.INFO,
)
configure_logging(level=_root_log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application")
    try:
        await startup_dependencies(
            app=app
        )
    except Exception:
        logger.critical("Failed to start application")
        raise

    yield

    logger.info("Shutting down application")
    try:
        await shutdown_dependencies(
            app=app
        )
        logger.info("Application shut down successfully")
    except Exception:
        logger.error("Error during application shutdown")


def create_app() -> FastAPI:
    assert_production_invariants()

    verify_gpu_availability()

    app = FastAPI(
        title=environment_variables.app_name,
        version=environment_variables.app_version,
        description=root_api_description(),
        openapi_tags=openapi_tags_metadata(),
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        swagger_ui_parameters={"persistAuthorization": True},
    )

    _add_middlewares(app)
    configure_cors(app)
    _include_routers(app)
    register_exception_handlers(app)

    from app.configuration.metrics import patch_instrumentator_routing
    patch_instrumentator_routing()

    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=[
            "/metrics",
            "/api/docs",
            "/api/redoc",
            "/api/openapi.json",
            "/api/v1/health",
            "/api/v1/ready",
        ],
        inprogress_name="aura_document_processing_http_requests_inprogress",
        inprogress_labels=True,
    ).instrument(app).expose(app, include_in_schema=False)

    install_openapi_bearer(app)

    logger.info("FastAPI application configured")
    return app


def _add_middlewares(app: FastAPI) -> None:
    add_authentication_middleware(app)
    add_logging_middleware(app)


def _include_routers(app: FastAPI) -> None:
    app.include_router(router, prefix="/api/v1")


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=environment_variables.app_host,
        port=environment_variables.app_port,
        reload=environment_variables.app_reload,
        log_level=environment_variables.log_level.lower(),
    )
