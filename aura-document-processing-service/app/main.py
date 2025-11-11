from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from app.application.services.ingestion_service import IngestionService
from app.configuration.logging_configuration import configure_logging
from app.application.exceptions.exceptions import AppError
from app.infrastructure.messaging.listener.document_listener import DocumentListener
from app.infrastructure.messaging.rabbitmq_client import RabbitmqClient
from app.infrastructure.persistence.repositories.database_client import DatabaseClient
from app.infrastructure.persistence.repositories.document_repository import DocumentRepository
from app.infrastructure.persistence.repositories.fragment_repository import FragmentRepository
from app.infrastructure.persistence.storages.document_storage_service import DocumentStorageService
from app.infrastructure.persistence.storages.minio_client import MinioClient


configure_logging(level=logging.INFO)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")

    db_client = DatabaseClient()
    rabbitmq = RabbitmqClient()
    minio = MinioClient()
    minio.ensure_bucket_exists()

    consumer = DocumentListener(rabbitmq)

    def process_message(message: dict):
        document_id = message.get("document_id")
        if document_id:
            with next(db_client.get_session()) as db:
                service = IngestionService(
                    document_repository=DocumentRepository(),
                    fragment_repository=FragmentRepository(),
                    document_storage_service=DocumentStorageService(minio),
                )
                service.process_document(document_id, db)

    consumer.start_consuming_background(
        callback=process_message,
        prefetch_count=1
    )

    logger.info("Application startup complete")

    yield

    logger.info("Shutting down application...")
    consumer.stop_consuming()
    rabbitmq.close()
    db_client.close()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Aura Document Processing Service",
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
    logging.exception("Unhandled server error")
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred"
        }
    )
