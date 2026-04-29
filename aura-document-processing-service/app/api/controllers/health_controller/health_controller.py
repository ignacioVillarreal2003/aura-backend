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

        redis_client = getattr(request.app.state, "redis_client", None)
        if redis_client is not None:
            try:
                await redis_client.client.ping()
                checks["redis"] = {"status": "ok"}
            except Exception as exc:
                logger.warning("Redis health check failed", exc_info=exc)
                checks["redis"] = {"status": "error"}
                overall_ok = False

        db_manager = getattr(request.app.state, "db_manager", None)
        if db_manager is not None:
            try:
                result = await db_manager.health_check()
                checks["database"] = result
                if result.get("status") != "healthy":
                    overall_ok = False
            except Exception as exc:
                logger.warning("Database health check failed", exc_info=exc)
                checks["database"] = {"status": "error"}
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
    description="Verifica dependencias y devuelve 200 o 503.",
    responses=_response_readiness,
)
