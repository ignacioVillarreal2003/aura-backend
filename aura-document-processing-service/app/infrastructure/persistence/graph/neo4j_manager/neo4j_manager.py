import asyncio
import logging
import time
from typing import Any, Optional
from urllib.parse import urlparse
from fastapi import HTTPException, Request, status
from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncManagedTransaction
from neo4j.exceptions import AuthError, Neo4jError, ServiceUnavailable

from app.infrastructure.persistence.graph.neo4j_manager.exceptions.neo4j_manager_exception import (
    Neo4jConnectionException,
    Neo4jManagerException,
    Neo4jNotStartedException,
)
from app.infrastructure.persistence.graph.neo4j_manager.interfaces.neo4j_manager_interface import (
    Neo4jManagerInterface,
)
from app.infrastructure.persistence.graph.neo4j_manager.neo4j_manager_settings import (
    Neo4jManagerSettings,
)
from app.infrastructure.persistence.graph.neo4j_manager.neo4j_schema_initializer import (
    Neo4jSchemaInitializer,
)

logger = logging.getLogger(__name__)

_TLS_SCHEMES = frozenset({"neo4j+s", "neo4j+ssc", "bolt+s", "bolt+ssc"})


class Neo4jManager(Neo4jManagerInterface):
    def __init__(
            self,
            neo4j_manager_settings: Optional[Neo4jManagerSettings] = None,
    ) -> None:
        self._settings = neo4j_manager_settings or Neo4jManagerSettings()
        self._driver: Optional[AsyncDriver] = None
        self._is_started: bool = False
        self._lifecycle_lock = asyncio.Lock()

    @property
    def settings(self) -> Neo4jManagerSettings:
        return self._settings

    @property
    def is_started(self) -> bool:
        return self._is_started

    @property
    def driver(self) -> AsyncDriver:
        if not self._is_started or self._driver is None:
            raise Neo4jNotStartedException(
                "The Neo4j manager is not started; call start() first.",
            )
        return self._driver

    @property
    def database(self) -> str:
        return self._settings.database

    def _build_driver_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "max_connection_pool_size": self._settings.pool_max_size,
            "connection_acquisition_timeout": self._settings.connection_acquisition_timeout_seconds,
            "connection_timeout": self._settings.connection_timeout_seconds,
            "max_transaction_retry_time": self._settings.max_transaction_retry_seconds,
        }
        scheme = (urlparse(self._settings.uri).scheme or "").lower()
        if scheme in _TLS_SCHEMES:
            return kwargs
        if self._settings.encrypted is not None:
            kwargs["encrypted"] = self._settings.encrypted
        return kwargs

    async def start(self) -> None:
        async with self._lifecycle_lock:
            if self._is_started:
                logger.debug("The Neo4j manager is already started; skipping.")
                return

            logger.info(
                "Starting the Neo4j driver.",
                extra={
                    "uri": self._settings.uri_safe,
                    "database": self._settings.database,
                    "pool_max_size": self._settings.pool_max_size,
                },
            )

            try:
                self._driver = AsyncGraphDatabase.driver(
                    self._settings.uri,
                    auth=(self._settings.user, self._settings.password.get_secret_value()),
                    **self._build_driver_kwargs(),
                )
                await self._verify_connection()

                if self._settings.apply_schema_on_startup:
                    initializer = Neo4jSchemaInitializer(
                        driver=self._driver,
                        database=self._settings.database,
                    )
                    await initializer.initialize()

                self._is_started = True
                logger.info(
                    "The Neo4j manager started successfully.",
                    extra={"database": self._settings.database},
                )

            except AuthError as e:
                await self._cleanup_driver()
                logger.exception("Neo4j authentication failed during startup.")
                raise Neo4jConnectionException("Neo4j authentication failed.") from e
            except (ServiceUnavailable, Neo4jError, OSError) as e:
                await self._cleanup_driver()
                logger.exception("The Neo4j manager failed to start.")
                raise Neo4jConnectionException(
                    "Could not connect to the Neo4j database."
                ) from e
            except Neo4jManagerException:
                await self._cleanup_driver()
                raise
            except Exception:
                await self._cleanup_driver()
                logger.exception("Unexpected error during Neo4j manager startup.")
                raise

    async def dispose(self) -> None:
        async with self._lifecycle_lock:
            if not self._is_started:
                logger.debug("The Neo4j manager is already disposed; nothing to do.")
                return
            logger.info("Disposing the Neo4j driver.")
            await self._cleanup_driver()
            self._is_started = False
            logger.info("The Neo4j driver was disposed successfully.")

    async def _verify_connection(self) -> None:
        assert self._driver is not None
        driver = self._driver
        timeout = self._settings.health_probe_timeout_seconds
        try:
            await asyncio.wait_for(driver.verify_connectivity(), timeout=timeout)

            async def _probe() -> None:
                async with driver.session(database=self._settings.database) as session:
                    result = await session.run("RETURN 1 AS health")
                    record = await result.single()
                    if record is None or record["health"] != 1:
                        raise Neo4jConnectionException(
                            "Neo4j health probe returned an unexpected value."
                        )

            await asyncio.wait_for(_probe(), timeout=timeout)
            logger.info(
                "The Neo4j connection was verified successfully.",
                extra={"database": self._settings.database},
            )
        except asyncio.TimeoutError as e:
            raise Neo4jConnectionException(
                "Neo4j connectivity verification timed out."
            ) from e

    async def health_check(self) -> dict[str, Any]:
        if not self._is_started or self._driver is None:
            return {
                "status": "unhealthy",
                "started": False,
                "error": "Neo4j manager is not started",
            }

        try:
            driver = self._driver
            start_time = time.monotonic()

            async def _probe() -> Any:
                async with driver.session(database=self._settings.database) as session:
                    result = await session.run("RETURN 1 AS health")
                    return await result.single()

            record = await asyncio.wait_for(
                _probe(),
                timeout=self._settings.health_probe_timeout_seconds,
            )
            latency_ms = round((time.monotonic() - start_time) * 1000, 2)
            healthy = record is not None and record.get("health") == 1
            return {
                "status": "healthy" if healthy else "unhealthy",
                "started": True,
                "latency_ms": latency_ms,
                "uri": self._settings.uri_safe,
                "database": self._settings.database,
            }
        except Exception:
            logger.warning("The Neo4j health check failed.")
            return {
                "status": "unhealthy",
                "started": True,
                "error": "Health probe failed",
            }

    async def execute_read(
            self,
            cypher: str,
            parameters: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        self._assert_started()
        params = parameters or {}
        try:
            async with self._driver.session(database=self._settings.database) as session:
                return await session.execute_read(self._collect_records, cypher, params)
        except Neo4jError as e:
            logger.exception(
                "A Neo4j read query failed.",
                extra={"neo4j_code": getattr(e, "code", None)},
            )
            raise Neo4jManagerException("A Neo4j read query failed.", status_code=500) from e
        except Exception as e:
            logger.exception("Unexpected error while executing a Neo4j read query.")
            raise Neo4jManagerException(
                "Unexpected error while executing a Neo4j read query.",
                status_code=500,
            ) from e

    async def execute_write(
            self,
            cypher: str,
            parameters: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        self._assert_started()
        params = parameters or {}
        try:
            async with self._driver.session(database=self._settings.database) as session:
                return await session.execute_write(self._collect_records, cypher, params)
        except Neo4jError as e:
            logger.exception(
                "A Neo4j write query failed.",
                extra={"neo4j_code": getattr(e, "code", None)},
            )
            raise Neo4jManagerException("A Neo4j write query failed.", status_code=500) from e
        except Exception as e:
            logger.exception("Unexpected error while executing a Neo4j write query.")
            raise Neo4jManagerException(
                "Unexpected error while executing a Neo4j write query.",
                status_code=500,
            ) from e

    @staticmethod
    async def _collect_records(
            tx: AsyncManagedTransaction,
            cypher: str,
            parameters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        result = await tx.run(cypher, parameters)
        records: list[dict[str, Any]] = []
        async for record in result:
            records.append(dict(record))
        return records

    def _assert_started(self) -> None:
        if not self._is_started or self._driver is None:
            raise Neo4jNotStartedException(
                "The Neo4j manager is not started; call start() first.",
            )

    async def _cleanup_driver(self) -> None:
        if self._driver is not None:
            try:
                await self._driver.close()
            except Exception:
                logger.warning("An error occurred while closing the Neo4j driver.")
        self._driver = None


async def get_neo4j_manager(
        request: Request,
) -> Neo4jManagerInterface:
    manager = getattr(request.app.state, "neo4j_manager", None)
    if manager is None:
        logger.error("The Neo4j manager was not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge graph storage is not configured",
        )
    if not manager.is_started:
        logger.error("The Neo4j manager exists on the application but has not been started.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge graph storage is not available",
        )
    return manager
