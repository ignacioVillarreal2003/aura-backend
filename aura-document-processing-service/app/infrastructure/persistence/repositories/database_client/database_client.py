import logging
from typing import Optional, Generator
from asyncio import Lock
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.infrastructure.persistence.repositories.database_client.database_client_configuration import \
    DatabaseClientConfiguration
from app.infrastructure.persistence.repositories.database_client.exceptions.database_client_exception import \
    DatabaseConnectionError, DatabaseClientNotInitializedError, DatabaseSessionError
from app.infrastructure.persistence.repositories.database_client.interfaces.database_client_interface import \
    DatabaseClientInterface

logger = logging.getLogger(__name__)


class DatabaseClient(DatabaseClientInterface):
    def __init__(
            self,
            database_client_configuration: DatabaseClientConfiguration
    ) -> None:
        self._database_client_configuration = database_client_configuration

        self._engine: Optional[Engine] = None
        self._session_local: Optional[sessionmaker] = None
        self._lock = Lock()

        logger.info("DatabaseClient initialized successfully")

    @classmethod
    def create(
            cls,
            db_driver: str,
            db_user: str,
            db_password: str,
            db_host: str,
            db_port: int,
            db_name: str,
            pool_size: Optional[int] = None,
            max_overflow: Optional[int] = None,
            pool_recycle: Optional[int] = None,
            pool_pre_ping: Optional[bool] = None,
            echo: Optional[bool] = None,
            pool_timeout: Optional[float] = None,
            connect_timeout: Optional[float] = None
    ) -> "DatabaseClient":
        config_kwargs = {}

        if db_driver is not None:
            config_kwargs['db_driver'] = db_driver
        if db_user is not None:
            config_kwargs['db_user'] = db_user
        if db_password is not None:
            config_kwargs['db_password'] = db_password
        if db_host is not None:
            config_kwargs['db_host'] = db_host
        if db_port is not None:
            config_kwargs['db_port'] = db_port
        if db_name is not None:
            config_kwargs['db_name'] = db_name
        if pool_size is not None:
            config_kwargs['pool_size'] = pool_size
        if max_overflow is not None:
            config_kwargs['max_overflow'] = max_overflow
        if pool_recycle is not None:
            config_kwargs['pool_recycle'] = pool_recycle
        if pool_pre_ping is not None:
            config_kwargs['pool_pre_ping'] = pool_pre_ping
        if echo is not None:
            config_kwargs['echo'] = echo
        if pool_timeout is not None:
            config_kwargs['pool_timeout'] = pool_timeout
        if connect_timeout is not None:
            config_kwargs['connect_timeout'] = connect_timeout

        database_client_configuration = DatabaseClientConfiguration(**config_kwargs)

        return cls(
            database_client_configuration=database_client_configuration
        )

    async def start(
            self
    ) -> None:
        async with self._lock:
            if self._engine is not None:
                logger.debug("DatabaseClient already started")
                return

            logger.info("Starting DatabaseClient connection pool")

            try:
                database_url = self._database_client_configuration.get_database_url()

                self._engine = create_engine(
                    database_url,
                    pool_pre_ping=self._database_client_configuration.pool_pre_ping,
                    pool_size=self._database_client_configuration.pool_size,
                    max_overflow=self._database_client_configuration.max_overflow,
                    pool_recycle=self._database_client_configuration.pool_recycle,
                    echo=self._database_client_configuration.echo,
                    pool_timeout=self._database_client_configuration.pool_timeout,
                    connect_args={'connect_timeout': self._database_client_configuration.connect_timeout}
                )

                self._session_local = sessionmaker(
                    autocommit=False,
                    autoflush=False,
                    bind=self._engine
                )

                with self._engine.connect() as connection:
                    connection.execute(text("SELECT 1"))

                logger.info("DatabaseClient started successfully")

            except Exception as e:
                logger.exception("Failed to initialize DatabaseClient")
                self._engine = None
                self._session_local = None
                raise DatabaseConnectionError("Failed to start database client") from e

    async def stop(self) -> None:
        async with self._lock:
            if self._engine is None:
                logger.debug("DatabaseClient already stopped")
                return

            logger.info("Stopping DatabaseClient connection pool")

            try:
                self._engine.dispose()
                logger.info("DatabaseClient stopped successfully")

            except Exception as e:
                logger.error(
                    "Error closing DatabaseClient",
                    extra={
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    },
                    exc_info=True
                )

            finally:
                self._engine = None
                self._session_local = None

    @property
    def is_started(self) -> bool:
        return self._engine is not None

    def get_session(self) -> Generator[Session, None, None]:
        if self._session_local is None:
            logger.error("Attempted to get session from uninitialized DatabaseClient")
            raise DatabaseClientNotInitializedError("DatabaseClient not started. Call start() first.")

        db = self._session_local()
        logger.debug("Database session created")

        try:
            yield db
        except Exception as e:
            logger.exception("Error during database session")
            db.rollback()
            raise DatabaseSessionError("Database session error") from e
        finally:
            db.close()
            logger.debug("Database session closed")

    async def health_check(self) -> bool:
        if self._engine is None:
            logger.warning("Health check failed: DatabaseClient not started")
            return False

        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.debug("Database health check passed")
            return True
        except Exception as e:
            logger.warning(
                "Database health check failed",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            return False
