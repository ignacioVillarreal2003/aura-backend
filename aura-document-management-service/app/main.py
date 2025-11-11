from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
import logging

from app.configuration.logging_configuration import configure_logging
from app.api.controllers import router
from app.application.exceptions.exceptions import AppError
from app.infrastructure.messaging.rabbitmq_client import RabbitmqClient
from app.infrastructure.persistence.repositories.database_client import DatabaseClient
from app.infrastructure.persistence.storages.minio_client import MinioClient


configure_logging(level=logging.INFO)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")

    db_client = DatabaseClient()
    if not db_client.health_check():
        logger.error("Database health check failed!")
        raise Exception("Cannot start application: Database is not available")

    rabbitmq = RabbitmqClient()

    minio = MinioClient()
    minio.ensure_bucket_exists()

    logger.info("Application startup complete")

    yield

    logger.info("Shutting down application...")

    rabbitmq.close()
    db_client.close()

    logger.info("Application shutdown complete")

app = FastAPI(
    title="Aura Document Management Service",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.exception_handler(AppError)
async def app_error_handler(_, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message}
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, exc: Exception):
    logger.exception("Unhandled server error")
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred"
        }
    )