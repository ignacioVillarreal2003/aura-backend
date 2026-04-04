import logging
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional
from fastapi import HTTPException, Request, status
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.infrastructure.persistence.database.database_manager.database_manager_settings import (
    DatabaseManagerSettings
)
from app.infrastructure.persistence.database.database_manager.exceptions.database_manager_exception import (
    DatabaseManagerException,
    DatabaseNotInitializedException,
    DatabaseSessionException
)
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import (
    DatabaseManagerInterface
)

logger = logging.getLogger(__name__)


class DatabaseManager(DatabaseManagerInterface):
    def __init__(self, database_manager_settings: Optional[DatabaseManagerSettings] = None) -> None:
        self._settings = database_manager_settings or DatabaseManagerSettings()

        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._is_initialized: bool = False

        self._metrics_lock = threading.Lock()
        self._connection_count: int = 0
        self._query_count: int = 0
        self._error_count: int = 0

    @property
    def settings(self) -> DatabaseManagerSettings:
        return self._settings

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized

    async def initialize(self) -> None:
        if self._is_initialized:
            logger.warning("DatabaseManager already initialized — skipping")
            return

        logger.info(
            "Initializing database connection",
            extra={
                "url": self._settings.url_safe,
                "pool_persistent_connections": self._settings.pool_persistent_connections,
                "pool_overflow_connections": self._settings.pool_overflow_connections
            }
        )

        try:
            self._engine = create_async_engine(
                self._settings.url,
                echo=self._settings.echo_sql,
                pool_size=self._settings.pool_persistent_connections,
                max_overflow=self._settings.pool_overflow_connections,
                pool_recycle=self._settings.pool_recycle_seconds,
                pool_pre_ping=self._settings.pool_liveness_probe,
                pool_timeout=self._settings.pool_checkout_timeout_seconds,
                pool_reset_on_return="rollback",
                isolation_level="READ COMMITTED",
                connect_args=self._settings.get_connect_args(),
                echo_pool=self._settings.echo_sql
            )

            self._setup_event_listeners()

            self._session_factory = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False
            )

            await self._verify_connection_with_retry()

            self._is_initialized = True
            logger.info(
                "Database initialized successfully",
                extra={
                    "pool_persistent_connections": self._settings.pool_persistent_connections,
                    "pool_overflow_connections": self._settings.pool_overflow_connections,
                    "ssl_enabled": self._settings.ssl_enabled
                }
            )

        except Exception as e:
            logger.exception("Failed to initialize database")
            await self.dispose()
            raise DatabaseManagerException(f"Failed to initialize database: {e}") from e

    async def dispose(self) -> None:
        if not self._engine:
            logger.debug("DatabaseManager already disposed — skipping")
            return

        logger.info("Disposing database engine")

        try:
            await self._engine.dispose()
            logger.info("Database engine disposed successfully")
        except Exception:
            logger.exception("Error disposing database engine")
        finally:
            self._engine = None
            self._session_factory = None
            self._is_initialized = False

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if not self._is_initialized or not self._session_factory:
            raise DatabaseNotInitializedException(
                "DatabaseManager is not initialized. Call initialize() first."
            )

        db_session = self._session_factory()
        try:
            yield db_session
            await db_session.commit()
        except DatabaseNotInitializedException:
            raise
        except HTTPException:
            raise
        except Exception as e:
            with self._metrics_lock:
                self._error_count += 1
            try:
                await db_session.rollback()
            except Exception:
                logger.exception("Failed to rollback session after error")
            raise DatabaseSessionException(f"Database session error: {e}") from e
        finally:
            await db_session.close()

    async def health_check(self) -> Dict[str, Any]:
        if not self._is_initialized or not self._engine:
            return {
                "status": "unhealthy",
                "initialized": False,
                "error": "Database not initialized"
            }

        try:
            start_time = time.monotonic()
            async with self._engine.connect() as conn:
                result = await conn.execute(text("SELECT 1 AS health"))
                row = result.scalar()
            latency_ms = round((time.monotonic() - start_time) * 1000, 2)

            pool = self._engine.pool
            return {
                "status": "healthy" if row == 1 else "unhealthy",
                "initialized": True,
                "latency_ms": latency_ms,
                "pool": {
                    "persistent_connections": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow_active": pool.overflow()
                },
                "metrics": self.get_metrics(),
                "settings": {
                    "pool_persistent_connections": self._settings.pool_persistent_connections,
                    "pool_overflow_connections": self._settings.pool_overflow_connections,
                    "pool_checkout_timeout_seconds": self._settings.pool_checkout_timeout_seconds,
                    "ssl_enabled": self._settings.ssl_enabled
                }
            }

        except Exception:
            logger.exception("Health check failed")
            return {
                "status": "unhealthy",
                "initialized": True,
                "error": "Health probe failed — see logs for details"
            }

    def get_metrics(self) -> Dict[str, int]:
        with self._metrics_lock:
            return {
                "connection_count": self._connection_count,
                "query_count": self._query_count,
                "error_count": self._error_count
            }

    async def __aenter__(self) -> "DatabaseManager":
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.dispose()

    async def _verify_connection_with_retry(self) -> None:
        if not self._engine:
            raise RuntimeError("Engine not initialised before connection verification")

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((DBAPIError, SQLAlchemyError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        async def _attempt() -> None:
            logger.info("Verifying database connection")
            async with self._engine.begin() as conn:
                result = await conn.execute(text("SELECT 1 AS health"))
                row = result.scalar()
                if row != 1:
                    raise RuntimeError("Health probe returned unexpected result")
            logger.info("Database connection verified successfully")

        await _attempt()

    def _setup_event_listeners(self) -> None:
        if not self._engine:
            return

        @event.listens_for(self._engine.sync_engine, "connect")
        def on_connect(dbapi_conn, connection_record) -> None:
            with self._metrics_lock:
                self._connection_count += 1
                count = self._connection_count
            logger.debug("Database connection established", extra={"total_connections": count})

        @event.listens_for(self._engine.sync_engine, "close")
        def on_close(dbapi_conn, connection_record) -> None:
            logger.debug("Database connection closed")

        @event.listens_for(self._engine.sync_engine, "checkout")
        def on_checkout(dbapi_conn, connection_record, connection_proxy) -> None:
            if self._settings.query_logging_enabled:
                logger.debug("Connection checked out from pool")

        @event.listens_for(self._engine.sync_engine, "checkin")
        def on_checkin(dbapi_conn, connection_record) -> None:
            if self._settings.query_logging_enabled:
                logger.debug("Connection returned to pool")

        @event.listens_for(self._engine.sync_engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany) -> None:
            with self._metrics_lock:
                self._query_count += 1

            if self._settings.query_logging_enabled:
                logger.debug(
                    "SQL executed",
                    extra={
                        "statement": statement,
                        "parameters": self._sanitize_parameters(parameters),
                        "executemany": executemany
                    }
                )

        @event.listens_for(self._engine.sync_engine, "handle_error")
        def handle_error(exception_context) -> None:
            with self._metrics_lock:
                self._error_count += 1
            logger.error(
                "Database engine error",
                extra={
                    "error": str(exception_context.original_exception),
                    "statement": (
                        str(exception_context.statement)
                        if exception_context.statement
                        else None
                    )
                }
            )

    _SENSITIVE_PARAM_KEYS = frozenset({"password", "token", "secret", "api_key", "auth"})

    @staticmethod
    def _sanitize_parameters(parameters: Any) -> Any:
        if not parameters:
            return parameters

        if isinstance(parameters, dict):
            sensitive = DatabaseManager._SENSITIVE_PARAM_KEYS
            return {
                k: "***" if any(s in k.lower() for s in sensitive) else v
                for k, v in parameters.items()
            }

        return parameters


async def get_database_manager(request: Request) -> DatabaseManagerInterface:
    try:
        database_manager: DatabaseManagerInterface = request.app.state.db_manager
        if not database_manager.is_initialized:
            logger.error("DatabaseManager found in app state but not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="DatabaseManager is not available"
            )
        return database_manager
    except AttributeError:
        logger.error("DatabaseManager not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DatabaseManager is not configured"
        )


async def get_database_session(request: Request):
    database_manager = await get_database_manager(request)

    try:
        async with database_manager.session() as session:
            yield session

    except HTTPException:
        raise

    except DatabaseNotInitializedException:
        logger.error("Database session requested but manager is not initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not available"
        )

    except DatabaseSessionException:
        logger.exception("Database session error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred"
        )
