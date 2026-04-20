import logging

from fastapi import Request, status, FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException, RequestValidationError

from app.application.exceptions.app_exception import AppException

logger = logging.getLogger(__name__)


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
    cause_chain = _build_cause_chain(exc)

    log_method = logger.error if exc.status_code >= 500 else logger.warning
    log_method(
        "Application error occurred",
        exc_info=exc,
        extra={
            "error_code": exc.code,
            "status_code": exc.status_code,
            "path": request.url.path,
            "cause_chain": cause_chain,
        },
    )

    content: dict = {"error": exc.code, "message": exc.message}
    if cause_chain:
        content["causes"] = cause_chain

    return JSONResponse(status_code=exc.status_code, content=content)


async def request_validation_exception_handler(
        request: Request,
        exc: RequestValidationError
) -> JSONResponse:
    logger.warning(
        "Request validation failed",
        extra={
            "errors": exc.errors(),
            "path": request.url.path,
        },
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "message": "Request validation failed",
            "detail": exc.errors(),
        },
    )


async def http_exception_handler(
        request: Request,
        exc: HTTPException
) -> JSONResponse:
    logger.warning(
        "HTTP exception occurred",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "HttpError", "message": exc.detail},
    )


async def general_exception_handler(
        request: Request,
        exc: Exception
) -> JSONResponse:
    logger.exception(
        "Unexpected error occurred",
        extra={
            "error_type": type(exc).__name__,
            "path": request.url.path,
        },
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "InternalServerError", "message": "An unexpected error occurred"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("Exception handlers registered successfully")
