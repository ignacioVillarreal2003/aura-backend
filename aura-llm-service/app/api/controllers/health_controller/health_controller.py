import asyncio
import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.controllers.health_controller.health_controller_interface import HealthControllerInterface
from app.api.openapi.common import ErrorBodyApp

logger = logging.getLogger(__name__)

_DEPENDENCY_CHECK_TIMEOUT_SECONDS = 2.0


class HealthController(HealthControllerInterface):
    async def liveness(self) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    async def readiness(self, request: Request) -> JSONResponse:
        checks: dict[str, object] = {}
        overall_ok = True

        http_client = getattr(request.app.state, "http_client", None)
        if http_client is not None:
            try:
                result = await asyncio.wait_for(
                    http_client.health_check(),
                    timeout=_DEPENDENCY_CHECK_TIMEOUT_SECONDS,
                )
                checks["http_client"] = result
                if result.get("status") not in ("healthy", "degraded"):
                    overall_ok = False
            except (Exception, asyncio.TimeoutError) as exc:
                logger.warning("HTTP client health check failed", exc_info=exc)
                checks["http_client"] = {"status": "error"}
                overall_ok = False
        else:
            checks["http_client"] = {"status": "not_configured"}
            overall_ok = False

        ollama_facade = getattr(request.app.state, "ollama_llm_facade", None)
        if ollama_facade is not None:
            try:
                healthy = await asyncio.wait_for(
                    ollama_facade.check_health(),
                    timeout=_DEPENDENCY_CHECK_TIMEOUT_SECONDS,
                )
                tools_bound = ollama_facade.tools_bound if healthy else False
                checks["ollama"] = {
                    "status": "ok" if healthy else "error",
                    "tools_bound": tools_bound,
                }
                if not healthy:
                    overall_ok = False
            except (Exception, asyncio.TimeoutError) as exc:
                logger.warning("Ollama facade health check failed", exc_info=exc)
                checks["ollama"] = {"status": "error", "tools_bound": False}
                overall_ok = False
        else:
            checks["ollama"] = {"status": "not_configured", "tools_bound": False}
            overall_ok = False

        redis_client = getattr(request.app.state, "redis_client", None)
        if redis_client is not None:
            try:
                redis_ok = await asyncio.wait_for(
                    redis_client.health_check(),
                    timeout=_DEPENDENCY_CHECK_TIMEOUT_SECONDS,
                )
                checks["redis"] = {"status": "ok" if redis_ok else "error"}
                if not redis_ok:
                    overall_ok = False
            except (Exception, asyncio.TimeoutError) as exc:
                logger.warning("Redis health check failed", exc_info=exc)
                checks["redis"] = {"status": "error"}
                overall_ok = False
        else:
            checks["redis"] = {"status": "not_configured"}
            overall_ok = False

        http_status = 200 if overall_ok else 503
        return JSONResponse(
            {"status": "ok" if overall_ok else "degraded", "checks": checks},
            status_code=http_status,
        )


router = APIRouter()
_health_controller = HealthController()

_response_liveness = {
    200: {
        "description": "Servicio activo",
        "content": {"application/json": {}},
    },
    500: {
        "description": "Error interno del servidor",
        "model": ErrorBodyApp,
    },
}
_response_readiness = {
    200: {
        "description": "Dependencias listas",
        "content": {"application/json": {}},
    },
    503: {
        "description": "Dependencias no disponibles",
        "content": {"application/json": {}},
    },
    500: {
        "description": "Error interno del servidor",
        "model": ErrorBodyApp,
    },
}

router.add_api_route(
    "/health",
    _health_controller.liveness,
    methods=["GET"],
    operation_id="liveness",
    summary="Estado de vida",
    description="Verifica que el servicio responde por HTTP.",
    responses=_response_liveness,
)
router.add_api_route(
    "/ready",
    _health_controller.readiness,
    methods=["GET"],
    operation_id="readiness",
    summary="Estado de preparación",
    description="Verifica dependencias (cliente HTTP, Ollama, Redis) y devuelve 200 o 503.",
    responses=_response_readiness,
)
