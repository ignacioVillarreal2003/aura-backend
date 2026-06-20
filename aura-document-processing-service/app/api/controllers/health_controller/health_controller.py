import logging
from collections.abc import Awaitable, Callable
from typing import Any
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.openapi.common import ErrorBodyApp
from app.infrastructure.persistence.memory_database.redis_client.interfaces.redis_client_interface import (
    RedisClientInterface,
)

logger = logging.getLogger(__name__)


class HealthController:
    async def liveness(self) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    async def readiness(self, request: Request) -> JSONResponse:
        state = request.app.state
        checks: dict[str, object] = {}
        overall_ok = True

        for name, attr, probe in self._critical_probes():
            dependency = getattr(state, attr, None)
            if dependency is None:
                logger.error("Readiness: critical dependency not registered", extra={"dependency": name})
                checks[name] = {"status": "not_registered"}
                overall_ok = False
                continue
            try:
                ok = await probe(dependency)
            except Exception as exc:
                logger.warning("%s health check failed", name, exc_info=exc)
                checks[name] = {"status": "error"}
                overall_ok = False
                continue
            checks[name] = {"status": "ok" if ok else "error"}
            if not ok:
                overall_ok = False

        http_status = 200 if overall_ok else 503
        return JSONResponse(
            {"status": "ok" if overall_ok else "degraded", "checks": checks},
            status_code=http_status,
        )

    @staticmethod
    def _critical_probes() -> list[tuple[str, str, Callable[[Any], Awaitable[bool]]]]:
        async def _probe_redis(client: RedisClientInterface) -> bool:
            await client.client.ping()
            return True

        async def _probe_healthy(manager: Any) -> bool:
            result = await manager.health_check()
            return result.get("status") == "healthy"

        return [
            ("redis", "redis_client", _probe_redis),
            ("database", "db_manager", _probe_healthy),
            ("rabbitmq", "rabbitmq_manager", _probe_healthy),
            ("object_storage", "minio_manager", _probe_healthy),
        ]


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
