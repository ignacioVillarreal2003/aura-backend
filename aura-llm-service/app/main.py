import logging
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.controllers import router
from app.api.handlers.exception_handlers import register_exception_handlers
from app.api.openapi.descriptions import openapi_tags_metadata, root_api_description
from app.api.openapi.swagger_bearer import install_openapi_bearer
from app.configuration.cors_configuration import configure_cors
from app.configuration.dependencies import shutdown_dependencies, startup_dependencies
from app.configuration.environment_variables import get_settings
from app.configuration.logging_configuration import configure_logging
from app.configuration.middlewares.authentication_middleware import add_authentication_middleware
from app.configuration.middlewares.body_size_limit_middleware import add_body_size_limit_middleware
from app.configuration.middlewares.guardrails_middleware import add_guardrails_middleware
from app.configuration.middlewares.logging_middleware import add_logging_middleware
from app.configuration.middlewares.output_guardrails_middleware import add_output_guardrails_middleware
from app.configuration.metrics import patch_instrumentator_routing
from app.configuration.tracing import setup_tracing

_settings = get_settings()
_root_log_level = getattr(
    logging,
    _settings.log_level,
    logging.INFO,
)
configure_logging(level=_root_log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(
        app: FastAPI
):
    logger.info("Starting application")
    settings = get_settings()
    if settings.is_development():
        settings.log_configuration()
    setup_tracing()
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
    app = FastAPI(
        title=_settings.app_name,
        version=_settings.app_version,
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
        inprogress_name="aura_llm_service_http_requests_inprogress",
        inprogress_labels=True,
    ).instrument(app).expose(app, include_in_schema=False)

    install_openapi_bearer(app)

    logger.info("FastAPI application configured")
    return app


def _add_middlewares(
        app: FastAPI
) -> None:
    add_output_guardrails_middleware(app)
    add_guardrails_middleware(app)
    add_body_size_limit_middleware(app)
    add_authentication_middleware(app)
    add_logging_middleware(app)


def _include_routers(
        app: FastAPI
) -> None:
    app.include_router(router, prefix="/api/v1")


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=_settings.app_host,
        port=_settings.app_port,
        reload=_settings.app_reload,
        log_level=_settings.log_level.lower(),
    )
