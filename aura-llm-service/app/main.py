import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from app.api.controllers import router
from app.application.ollama_configurator.ollama_configurator import OllamaConfigurator
from app.configuration.logging_configuration import configure_logging
from app.application.exceptions.app_exceptions import AppError
from app.infrastructure.http.http_client import HttpClient
from app.application.services.document_question_service import DocumentQuestionService

configure_logging(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")

    http_client = HttpClient()
    http_client.start()
    app.state.http_client = http_client

    ollama_configurator = OllamaConfigurator()
    app.state.ollama_configurator = ollama_configurator

    app.state.document_question_service = DocumentQuestionService(http_client=app.state.http_client,
                                                                  ollama_configurator=app.state.ollama_configurator)

    yield

    logger.info("Shutting down application...")

    await http_client.stop()


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

app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.exception_handler(AppError)
async def app_error_handler(_, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.code,
            "message": exc.message
        }
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, exc: Exception):
    logger.exception("Unhandled server error")
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "Ha ocurrido un error inesperado"
        }
    )
