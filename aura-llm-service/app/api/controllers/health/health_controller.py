import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.openapi.common import ErrorBodyApp

logger = logging.getLogger(__name__)


class HealthController:
    async def liveness(self) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    async def readiness(self, request: Request) -> JSONResponse:
        checks: dict[str, object] = {}
        overall_ok = True

        http_client = getattr(request.app.state, "http_client", None)
        if http_client is not None:
            try:
                result = await http_client.health_check()
                checks["http_client"] = result
                if result.get("status") not in ("healthy", "degraded"):
                    overall_ok = False
            except Exception as exc:
                logger.warning("HTTP client health check failed", exc_info=exc)
                checks["http_client"] = {"status": "error"}
                overall_ok = False
        else:
            checks["http_client"] = {"status": "not_configured"}
            overall_ok = False

        ollama_facade = getattr(request.app.state, "ollama_llm_facade_base", None)
        if ollama_facade is not None:
            try:
                initialized = bool(getattr(ollama_facade, "_initialized", False))
                checks["ollama"] = {
                    "status": "ok" if initialized else "error",
                }
                if not initialized:
                    overall_ok = False
            except Exception as exc:
                logger.warning("Ollama facade health check failed", exc_info=exc)
                checks["ollama"] = {"status": "error"}
                overall_ok = False
        else:
            checks["ollama"] = {"status": "not_configured"}
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
    description="Verifica dependencias (cliente HTTP, Ollama) y devuelve 200 o 503.",
    responses=_response_readiness,
)
