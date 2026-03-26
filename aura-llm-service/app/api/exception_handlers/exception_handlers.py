from fastapi import Request, status, FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
import logging

from app.application.exceptions.app_exception import AppException

logger = logging.getLogger(__name__)


async def app_exception_handler(
        request: Request,
        exc: AppException
) -> JSONResponse:
    logger.warning(
        "Application error occurred",
        extra={
            "error_code": exc.code,
            "error_message": exc.message,
            "status_code": exc.status_code,
            "path": request.url.path
        }
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.code,
            "message": exc.message,
            "details": None
        }
    )


async def http_exception_handler(
        request: Request,
        exc: HTTPException
) -> JSONResponse:
    logger.warning(
        "HTTP exception occurred",
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
            "details": None
        }
    )


async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError
) -> JSONResponse:
    errors = exc.errors()

    logger.warning(
        "Request validation error",
        extra={
            "error_type": "RequestValidationError",
            "errors": errors,
            "path": request.url.path
        }
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "RequestValidationError",
            "message": "Request validation failed",
            "details": errors
        }
    )


async def general_exception_handler(
        request: Request,
        exc: Exception
) -> JSONResponse:
    logger.exception(
        "Unexpected error occurred",
        extra={
            "error_type": type(exc).__name__,
            "path": request.url.path
        }
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "details": None
        }
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("Exception handlers registered successfully")
