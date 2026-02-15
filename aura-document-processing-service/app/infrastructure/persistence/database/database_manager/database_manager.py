import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Dict, Any
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.exc import SQLAlchemyError, DBAPIError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential, before_sleep_log

from app.infrastructure.persistence.database.database_manager.database_manager_settings import DatabaseManagerSettings
from app.infrastructure.persistence.database.database_manager.exceptions.database_manager_exception import (
    DatabaseManagerException,
    DatabaseNotInitializedException
)
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import (
    DatabaseManagerInterface
)

logger = logging.getLogger(__name__)


class DatabaseManager(DatabaseManagerInterface):
    def __init__(
            self,
            database_manager_settings: DatabaseManagerSettings
    ) -> None:
        self._database_manager_settings = database_manager_settings

        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._is_initialized = False

        self._connection_count = 0
        self._query_count = 0
        self._error_count = 0
        self._last_health_check: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
            cls,
            user: str,
            password: str,
            host: str,
            port: int,
            name: str,
            driver: str = "postgresql",
            **config_kwargs
    ) -> "DatabaseManager":
        database_manager_settings = DatabaseManagerSettings(
            user=user,
            password=password,
            host=host,
            port=port,
            name=name,
            driver=driver,
            **config_kwargs
        )

        return cls(
            database_manager_settings=database_manager_settings
        )

    @property
    def settings(
            self
    ) -> DatabaseManagerSettings:
        return self._database_manager_settings

    @property
    def is_initialized(
            self
    ) -> bool:
        return self._is_initialized

    async def initialize(
            self
    ) -> None:
        if self._is_initialized:
            logger.warning("DatabaseManager already initialized")
            return

        logger.info(
            "Initializing database connection",
            extra={
                "url": self.settings.url_safe,
                "pool_size": self.settings.pool_size,
                "max_overflow": self.settings.max_overflow,
            }
        )

        try:
            self._engine = create_async_engine(
                self.settings.url,
                echo=self.settings.echo,
                pool_size=self.settings.pool_size,
                max_overflow=self.settings.max_overflow,
                pool_recycle=self.settings.pool_recycle,
                pool_pre_ping=self.settings.pool_pre_ping,
                pool_timeout=self.settings.pool_timeout,
                pool_reset_on_return="rollback",
                isolation_level="READ COMMITTED",
                connect_args={
                    "timeout": self.settings.connect_timeout,
                    "server_settings": {
                        "application_name": self.settings.application_name,
                        "jit": "off",
                    },
                    "command_timeout": self.settings.statement_timeout,
                },
                echo_pool=self.settings.echo and self.settings.enable_query_logging,
            )

            self._setup_event_listeners()

            self._session_factory = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )

            await self._verify_connection_with_retry()

            self._is_initialized = True
            logger.info(
                "Database initialized successfully",
                extra={
                    "pool_size": self.settings.pool_size,
                    "max_overflow": self.settings.max_overflow,
                }
            )

        except Exception as e:
            logger.exception(
                "Failed to initialize database",
                extra={
                    "error": str(e)
                }
            )
            await self.dispose()
            raise DatabaseManagerException(f"Failed to initialize database: {str(e)}") from e

    def _setup_event_listeners(
            self
    ) -> None:
        if not self._engine:
            return

        @event.listens_for(
            self._engine.sync_engine,
            "connect"
        )
        def on_connect(dbapi_conn, connection_record) -> None:
            self._connection_count += 1
            logger.debug(
                "Database connection established",
                extra={
                    "total_connections": self._connection_count
                }
            )

        @event.listens_for(
            self._engine.sync_engine,
            "checkout"
        )
        def on_checkout(dbapi_conn, connection_record, connection_proxy) -> None:
            if self.settings.enable_query_logging:
                logger.debug("Connection checked out from pool")

        @event.listens_for(
            self._engine.sync_engine,
            "checkin"
        )
        def on_checkin(dbapi_conn, connection_record) -> None:
            if self.settings.enable_query_logging:
                logger.debug("Connection returned to pool")

        @event.listens_for(
            self._engine.sync_engine,
            "close"
        )
        def on_close(dbapi_conn, connection_record) -> None:
            logger.debug("Database connection closed")

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
            self._query_count += 1
            if self.settings.enable_query_logging:
                safe_params = self._sanitize_parameters(parameters)
                logger.debug(
                    "SQL executed",
                    extra={
                        "statement": statement,
                        "parameters": safe_params,
                        "executemany": executemany,
                    },
                )

        @event.listens_for(
            self._engine.sync_engine,
            "handle_error"
        )
        def handle_error(exception_context) -> None:
            self._error_count += 1
            logger.error(
                "Database error occurred",
                extra={
                    "error": str(exception_context.original_exception),
                    "statement": str(exception_context.statement) if exception_context.statement else None,
                },
            )

    @staticmethod
    def _sanitize_parameters(
            parameters: Any
    ) -> Any:
        if not parameters:
            return parameters

        if isinstance(parameters, dict):
            sensitive_keys = {'password', 'token', 'secret', 'api_key', 'auth'}
            return {
                k: '***' if any(sens in k.lower() for sens in sensitive_keys) else v
                for k, v in parameters.items()
            }

        return parameters

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=2,
            max=10
        ),
        retry=retry_if_exception_type(
            (DBAPIError, SQLAlchemyError)
        ),
        before_sleep=before_sleep_log(
            logger,
            logging.WARNING
        ),
        reraise=True,
    )
    async def _verify_connection_with_retry(self) -> None:
        if not self._engine:
            raise RuntimeError("Engine not initialized")

        logger.info("Verifying database connection...")

        try:
            async with self._engine.begin() as conn:
                result = await conn.execute(text("SELECT 1 as health"))
                row = result.scalar()
                if row != 1:
                    raise RuntimeError("Health check failed: unexpected result")

            logger.info("Database connection verified successfully")

        except Exception as e:
            logger.error(f"Database connection verification failed: {str(e)}")
            raise

    async def dispose(
            self
    ) -> None:
        if self._engine:
            logger.info("Disposing database engine")
            try:
                await self._engine.dispose()
                logger.info("Database engine disposed successfully")
            except Exception as e:
                logger.error(f"Error disposing database engine: {str(e)}")

        self._engine = None
        self._session_factory = None
        self._is_initialized = False

    @asynccontextmanager
    async def session(
            self
    ) -> AsyncGenerator[AsyncSession, None]:
        if (not self._is_initialized or
                not self._session_factory):
            raise DatabaseNotInitializedException("DatabaseManager not initialized. Call initialize() first.")

        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            self._error_count += 1
            await session.rollback()
            logger.error(
                "Database session error",
                extra={
                    "error": str(e)
                },
                exc_info=True
            )
            raise
        finally:
            await session.close()

    async def health_check(
            self
    ) -> Dict[str, Any]:
        if (not self._is_initialized or
                not self._engine):
            health_data = {
                "status": "unhealthy",
                "initialized": False,
                "error": "Database not initialized",
                "timestamp": time.time(),
            }
            self._last_health_check = health_data
            return health_data

        try:
            start_time = time.time()

            async with self._engine.connect() as conn:
                result = await conn.execute(text("SELECT 1 as health"))
                row = result.scalar()

            latency_ms = (time.time() - start_time) * 1000

            pool = self._engine.pool

            health_data = {
                "status": "healthy" if row == 1 else "unhealthy",
                "initialized": True,
                "latency_ms": round(latency_ms, 2),
                "timestamp": time.time(),
                "pool": {
                    "size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                    "total_connections": self._connection_count,
                },
                "metrics": {
                    "total_queries": self._query_count,
                    "total_errors": self._error_count,
                },
                "settings": {
                    "pool_size": self.settings.pool_size,
                    "max_overflow": self.settings.max_overflow,
                    "pool_timeout": self.settings.pool_timeout,
                },
            }

            self._last_health_check = health_data
            return health_data

        except Exception as e:
            logger.exception("Health check failed")
            health_data = {
                "status": "unhealthy",
                "initialized": True,
                "error": str(e),
                "timestamp": time.time(),
            }
            self._last_health_check = health_data
            return health_data

    def get_metrics(
            self
    ) -> Dict[str, int]:
        return {
            "connection_count": self._connection_count,
            "query_count": self._query_count,
            "error_count": self._error_count,
        }

    async def __aenter__(
            self
    ):
        await self.initialize()
        return self

    async def __aexit__(
            self,
            exc_type,
            exc_val,
            exc_tb
    ):
        await self.dispose()
