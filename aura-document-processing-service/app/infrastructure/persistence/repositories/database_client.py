import logging
import threading
from typing import Optional, Generator
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.configuration.environment_variables import environment_variables
from app.application.exceptions.exceptions import DatabaseError


logger = logging.getLogger(__name__)


class DatabaseClient:
    _instance: Optional['DatabaseClient'] = None
    _lock: threading.Lock = threading.Lock()
    _initialized: bool = False

    def __new__(cls) -> 'DatabaseClient':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            self.engine: Optional[Engine] = None
            self.SessionLocal: Optional[sessionmaker] = None
            self._connect()
            self._initialized = True

    def _connect(self) -> None:
        try:
            database_url = (
                f"{environment_variables.db_driver}://{environment_variables.db_user}:"
                f"{environment_variables.db_password}@{environment_variables.db_host}:"
                f"{environment_variables.db_port}/{environment_variables.db_name}"
            )

            self.engine = create_engine(
                database_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                pool_recycle=3600,
                echo=False,
            )

            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )

            logger.info(
                "Database client initialized successfully",
                extra={
                    "db_host": environment_variables.db_host,
                    "db_name": environment_variables.db_name,
                    "db_driver": environment_variables.db_driver
                }
            )

        except Exception as e:
            logger.exception("Failed to initialize database connection")
            raise DatabaseError("Failed to initialize database connection") from e

    def get_session(self) -> Generator[Session, None, None]:
        if self.SessionLocal is None:
            raise DatabaseError("Database client not initialized")

        db = self.SessionLocal()
        logger.debug("Database session created")

        try:
            yield db
        except Exception as e:
            logger.exception("Error during database session")
            db.rollback()
            raise
        finally:
            db.close()
            logger.debug("Database session closed")

    def close(self) -> None:
        try:
            if self.engine:
                self.engine.dispose()
                logger.info("Database connection pool closed")
        except Exception as e:
            logger.warning("Error closing database connection pool", exc_info=e)

    def health_check(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.debug("Database health check passed")
            return True
        except Exception as e:
            logger.warning("Database health check failed", exc_info=e)
            return False