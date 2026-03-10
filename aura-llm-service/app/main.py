import logging
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.controllers import router
from app.configuration.dependencies import startup_dependencies, shutdown_dependencies
from app.configuration.logging_configuration import configure_logging
from app.configuration.environment_variables import environment_variables

configure_logging(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(
        app: FastAPI
):
    logger.info("Starting FastAPI Application")

    try:
        await startup_dependencies()
        logger.info("Application started successfully")

    except Exception:
        logger.critical("Failed to start application")
        raise

    yield

    logger.info("Shutting down FastAPI Application")

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
    add_exception_handlers(app)

    logger.info("FastAPI application configured")

    return app


def configure_cors(
        app: FastAPI
) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=environment_variables.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    logger.debug("CORS configured")


def add_middleware(
        app: FastAPI
) -> None:
    @app.middleware(
        "http"
    )
    async def log_requests(
            request: Request,
            call_next
    ):
        logger.info(f"Request: {request.method} {request.url.path}")

        response = await call_next(request)

        logger.info(f"Response: {response.status_code}")

        return response

    logger.debug("Middleware added")


def include_routers(
        app: FastAPI
) -> None:
    app.include_router(
        router,
        prefix="/api"
    )

    @app.get(
        "/health",
        tags=["Health"]
    )
    async def health_check():
        return {
            "status": "healthy",
            "app": environment_variables.app_name,
            "version": environment_variables.app_version
        }

    logger.debug("Routers included")


def add_exception_handlers(
        app: FastAPI
) -> None:
    @app.exception_handler(
        StarletteHTTPException
    )
    async def http_exception_handler(
            request: Request,
            exc: StarletteHTTPException
    ):
        logger.warning(
            f"HTTP exception: {exc.status_code}",
            extra={
                "status_code": exc.status_code,
                "detail": exc.detail,
                "path": request.url.path
            }
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTPException",
                "message": exc.detail,
                "status_code": exc.status_code
            }
        )

    @app.exception_handler(
        RequestValidationError
    )
    async def validation_exception_handler(
            request: Request,
            exc: RequestValidationError
    ):
        logger.warning(
            "Validation error",
            extra={
                "path": request.url.path,
                "errors": exc.errors()
            }
        )

        return JSONResponse(
            status_code=422,
            content={
                "error": "ValidationError",
                "message": "Request validation failed",
                "details": exc.errors()
            }
        )

    @app.exception_handler(
        Exception
    )
    async def general_exception_handler(
            request: Request,
            exc: Exception
    ):
        logger.exception(
            "Unexpected error",
            extra={
                "path": request.url.path,
                "error_type": type(exc).__name__
            }
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred"
            }
        )

    logger.debug("Exception handlers added")


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=environment_variables.app_host,
        port=environment_variables.app_port,
        reload=environment_variables.app_reload,
        log_level=environment_variables.log_level.lower()
    )
