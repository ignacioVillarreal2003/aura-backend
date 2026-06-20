import logging
from typing import Any
from fastapi import Request, status, FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException, RequestValidationError

from app.application.exceptions.app_exception import AppException

logger = logging.getLogger(__name__)


def _get_request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _build_cause_chain(exc: BaseException) -> list[str]:
    chain: list[str] = []
    current = exc.__cause__
    while current is not None:
        chain.append(f"{type(current).__name__}: {current}")
        current = getattr(current, "__cause__", None)
    return chain


async def app_exception_handler(
        request: Request,
        exc: AppException
) -> JSONResponse:
    request_id = _get_request_id(request)
    cause_chain = _build_cause_chain(exc)

    log_method = logger.error if exc.status_code >= 500 else logger.warning
    log_method(
        "Application error occurred",
        exc_info=exc,
        extra={
            "request_id": request_id,
            "error_code": exc.code,
            "status_code": exc.status_code,
            "path": request.url.path,
            "cause_chain": cause_chain,
        },
    )

    content: dict[str, Any] = {"error": exc.code, "message": exc.message}
    if request_id:
        content["request_id"] = request_id

    headers = {"X-Request-ID": request_id} if request_id else {}
    return JSONResponse(status_code=exc.status_code, content=content, headers=headers)


async def request_validation_exception_handler(
        request: Request,
        exc: RequestValidationError
) -> JSONResponse:
    request_id = _get_request_id(request)
    errors = jsonable_encoder(exc.errors())
    logger.warning(
        "Request validation failed",
        extra={
            "request_id": request_id,
            "errors": errors,
            "path": request.url.path,
        },
    )
    content: dict[str, Any] = {
        "error": "ValidationError",
        "message": "Request validation failed",
        "detail": errors,
    }
    if request_id:
        content["request_id"] = request_id

    headers = {"X-Request-ID": request_id} if request_id else {}
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=content,
        headers=headers,
    )


async def http_exception_handler(
        request: Request,
        exc: HTTPException
) -> JSONResponse:
    request_id = _get_request_id(request)
    logger.warning(
        "HTTP exception occurred",
        extra={
            "request_id": request_id,
            "status_code": exc.status_code,
            "path": request.url.path,
        },
    )
    content: dict[str, Any] = {"error": "HttpError", "message": exc.detail}
    if request_id:
        content["request_id"] = request_id

    headers = dict(exc.headers or {})
    if request_id:
        headers["X-Request-ID"] = request_id
    return JSONResponse(status_code=exc.status_code, content=content, headers=headers)


async def general_exception_handler(
        request: Request,
        exc: Exception
) -> JSONResponse:
    request_id = _get_request_id(request)
    logger.exception(
        "Unexpected error occurred",
        extra={
            "request_id": request_id,
            "error_type": type(exc).__name__,
            "path": request.url.path,
        },
    )
    content: dict[str, Any] = {
        "error": "InternalServerError",
        "message": "An unexpected error occurred",
    }
    if request_id:
        content["request_id"] = request_id

    headers = {"X-Request-ID": request_id} if request_id else {}
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content,
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("Exception handlers registered successfully")
