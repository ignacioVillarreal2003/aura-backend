from fastapi import FastAPI
from contextlib import asynccontextmanager
import threading
import logging
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from app.configuration.database_session_manager import DatabaseSessionManager
from app.configuration.logging_configuration import configure_logging
from app.application.exceptions.exceptions import AppError
from app.infrastructure.messaging.listener.rabbitmq_document_listener import RabbitMQDocumentListener


configure_logging(level=logging.INFO)

logger = logging.getLogger(__name__)

consumer = RabbitMQDocumentListener(db_session_manager=DatabaseSessionManager())


@asynccontextmanager
async def lifespan(app: FastAPI):
    thread = threading.Thread(target=consumer.start_consuming, daemon=True)
    thread.start()
    logger.info("RabbitMQ consumer started in background thread")

    yield

    consumer.close()
    logger.info("RabbitMQ consumer closed")


app = FastAPI(
    title="Aura Document Processing Service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
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
