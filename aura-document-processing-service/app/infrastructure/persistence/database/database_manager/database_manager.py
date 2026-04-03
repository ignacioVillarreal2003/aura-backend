import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional
from fastapi import HTTPException, Request, status
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.application.exceptions.app_exception import AppException
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

_SQL_DEBUG_LOG_MAX_LENGTH = 240


class DatabaseManager(DatabaseManagerInterface):
    def __init__(
            self,
            database_manager_settings: Optional[DatabaseManagerSettings] = None
    ) -> None:
        self._settings = database_manager_settings or DatabaseManagerSettings()

        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._is_initialized: bool = False

        self._lifecycle_lock = asyncio.Lock()

    @property
    def settings(
            self
    ) -> DatabaseManagerSettings:
        return self._settings

    @property
    def is_initialized(
            self
    ) -> bool:
        return self._is_initialized

    async def initialize(
            self
    ) -> None:
        async with self._lifecycle_lock:
            if self._is_initialized:
                logger.debug("The database manager is already initialized; skipping.")
                return

            logger.info(
                "Initializing the database engine and connection pool.",
                extra={
                    "database_url_redacted": self._settings.url_safe,
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
                    "The database was initialized successfully.",
                    extra={
                        "pool_persistent_connections": self._settings.pool_persistent_connections,
                        "pool_overflow_connections": self._settings.pool_overflow_connections,
                        "ssl_enabled": self._settings.ssl_enabled
                    }
                )

            except Exception as e:
                logger.exception("The database manager failed to initialize.")
                await self._cleanup_resources()
                raise DatabaseManagerException(
                    "Could not initialize the database connection.",
                    status_code=503
                ) from e

    async def dispose(
            self
    ) -> None:
        async with self._lifecycle_lock:
            if not self._is_initialized:
                logger.debug("The database manager is already disposed; nothing to do.")
                return

            logger.info("Disposing the database engine.")
            await self._cleanup_resources()
            logger.info("The database engine was disposed successfully.")

    @asynccontextmanager
    async def session(
            self
    ) -> AsyncIterator[AsyncSession]:
        if not self._is_initialized or not self._session_factory:
            raise DatabaseNotInitializedException("The database manager is not initialized; call initialize() first.")

        db_session = self._session_factory()
        try:
            yield db_session
            await db_session.commit()
        except DatabaseNotInitializedException:
            raise
        except HTTPException:
            raise
        except AppException:
            try:
                await db_session.rollback()
            except Exception:
                logger.exception("The session could not be rolled back after an application error.", )
            raise
        except Exception as e:
            try:
                await db_session.rollback()
            except Exception:
                logger.exception("The session could not be rolled back after an error.")
            raise DatabaseSessionException("A database error occurred while using the session.") from e
        finally:
            await db_session.close()

    async def health_check(
            self
    ) -> dict[str, Any]:
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
                "settings": {
                    "pool_persistent_connections": self._settings.pool_persistent_connections,
                    "pool_overflow_connections": self._settings.pool_overflow_connections,
                    "pool_checkout_timeout_seconds": self._settings.pool_checkout_timeout_seconds,
                    "ssl_enabled": self._settings.ssl_enabled
                }
            }

        except Exception:
            logger.exception("The database health check failed.")
            return {
                "status": "unhealthy",
                "initialized": True,
                "error": "Health probe failed; see logs for details."
            }

    async def __aenter__(
            self
    ) -> "DatabaseManager":
        await self.initialize()
        return self

    async def __aexit__(
            self,
            exc_type,
            exc_val,
            exc_tb
    ) -> None:
        await self.dispose()

    async def _verify_connection_with_retry(
            self
    ) -> None:
        if not self._engine:
            raise RuntimeError("Engine not initialised before connection verification")

        @retry(
            stop=stop_after_attempt(self._settings.retry_max_attempts),
            wait=wait_exponential(
                min=self._settings.retry_backoff_min_seconds,
                max=self._settings.retry_backoff_max_seconds
            ),
            retry=retry_if_exception_type((DBAPIError, SQLAlchemyError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
        async def _attempt() -> None:
            logger.info("Verifying connectivity to the database.")
            async with self._engine.begin() as conn:
                result = await conn.execute(text("SELECT 1 AS health"))
                row = result.scalar()
                if row != 1:
                    raise RuntimeError("Health probe returned unexpected result")
            logger.info("The database connection was verified successfully.")

        await _attempt()

    def _setup_event_listeners(
            self
    ) -> None:
        if not self._engine:
            return

        @event.listens_for(
            self._engine.sync_engine,
            "connect"
        )
        def on_connect(
                dbapi_conn,
                connection_record
        ) -> None:
            logger.debug("A new database connection was opened.")

        @event.listens_for(
            self._engine.sync_engine,
            "close"
        )
        def on_close(
                dbapi_conn,
                connection_record
        ) -> None:
            logger.debug("A database connection was closed.")

        @event.listens_for(
            self._engine.sync_engine,
            "checkout"
        )
        def on_checkout(
                dbapi_conn,
                connection_record,
                connection_proxy
        ) -> None:
            if self._settings.query_logging_enabled:
                logger.debug("A connection was checked out from the pool.")

        @event.listens_for(
            self._engine.sync_engine,
            "checkin"
        )
        def on_checkin(
                dbapi_conn,
                connection_record
        ) -> None:
            if self._settings.query_logging_enabled:
                logger.debug("A connection was returned to the pool.")

        @event.listens_for(
            self._engine.sync_engine,
            "after_cursor_execute"
        )
        def after_cursor_execute(
                conn,
                cursor,
                statement,
                parameters,
                context,
                executemany
        ) -> None:
            if self._settings.query_logging_enabled:
                stmt = statement or ""
                truncated = len(stmt) > _SQL_DEBUG_LOG_MAX_LENGTH
                snippet = stmt[:_SQL_DEBUG_LOG_MAX_LENGTH] if truncated else stmt
                logger.debug(
                    "A SQL statement was executed (debug logging; not for production traffic).",
                    extra={
                        "statement_snippet": snippet,
                        "statement_truncated": truncated,
                        "statement_length": len(stmt),
                        "executemany": executemany
                    }
                )

        @event.listens_for(
            self._engine.sync_engine,
            "handle_error"
        )
        def handle_error(exception_context) -> None:
            orig = exception_context.original_exception
            stmt = exception_context.statement
            stmt_len = len(str(stmt)) if stmt is not None else 0
            logger.error(
                "The database engine reported an error.",
                extra={
                    "exception_type": type(orig).__name__ if orig is not None else None,
                    "statement_length": stmt_len
                }
            )

    async def _cleanup_resources(
            self
    ) -> None:
        if self._engine and not self._engine.is_disposed:
            try:
                await self._engine.dispose()
            except Exception:
                logger.exception("An error occurred while disposing the database engine.")

        self._engine = None
        self._session_factory = None
        self._is_initialized = False


async def get_database_manager(
        request: Request
) -> DatabaseManagerInterface:
    try:
        database_manager: DatabaseManagerInterface = request.app.state.db_manager
        if not database_manager.is_initialized:
            logger.error("The database manager exists on the application but has not been initialized.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="DatabaseManager is not available"
            )
        return database_manager
    except AttributeError:
        logger.error("The database manager was not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DatabaseManager is not configured"
        )


async def get_database_session(
        request: Request
) -> AsyncIterator[AsyncSession]:
    database_manager: DatabaseManagerInterface = await get_database_manager(request)

    try:
        async with database_manager.session() as session:
            yield session

    except HTTPException:
        raise

    except DatabaseNotInitializedException:
        logger.error("A database session was requested but the manager is not initialized.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not available"
        )

    except DatabaseSessionException:
        logger.exception("A database session error occurred.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred"
        )

    except AppException:
        raise
