from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
import logging
from app.configuration.logging_configuration import configure_logging

from app.api.controllers import router
from app.application.exceptions.exceptions import AppError


configure_logging(level=logging.INFO)

app = FastAPI(
    title="Aura Document Management Service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
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
    return JSONResponse(status_code=exc.status_code, content={"error": exc.code, "message": exc.message})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, exc: Exception):
    logging.exception("Unhandled server error")
    return JSONResponse(status_code=500, content={"error": "InternalServerError", "message": "An unexpected error occurred"})