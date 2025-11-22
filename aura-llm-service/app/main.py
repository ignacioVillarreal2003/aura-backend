from contextlib import asynccontextmanager

from fastapi import FastAPI
import logging
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from app.api.controllers import router
from app.application.services.interfaces.question_service_interface import QuestionServiceInterface
from app.application.services.llm_service import LLMService
from app.application.services.question_service import QuestionService
from app.configuration.dependencies import get_question_listener
from app.configuration.logging_configuration import configure_logging
from app.application.exceptions.api_exceptions import AppError
from app.infrastructure.messaging.rabbitmq_client import RabbitmqClient

configure_logging(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")

    logger.info("Starting RabbitMQ consumer thread...")
    rabbitmq_client = RabbitmqClient()
    llm_service = LLMService()
    question_service = QuestionService(llm_service)

    listener = get_question_listener(rabbitmq_client, question_service)
    listener.start_consuming_background()

    logger.info("RabbitMQ consumer started.")

    yield

    logger.info("Shutting down application...")

    listener.stop_consuming()

    logger.info("Application shutdown complete")


app = FastAPI(title="Aura Document Processing Service",
              version="1.0.0",
              lifespan=lifespan)
app.add_middleware(CORSMiddleware,
                   allow_origins=["*"],
                   allow_credentials=True,
                   allow_methods=["*"],
                   allow_headers=["*"])
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
    logging.exception("Unhandled server error")
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "Ha ocurrido un error inesperado"
        }
    )
