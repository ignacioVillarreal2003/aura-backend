import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from app.configuration.environment_variables import environment_variables


logger = logging.getLogger(__name__)


class DatabaseSessionManager:
    def __init__(self):
        database_url = (
            f"{environment_variables.db_driver}://{environment_variables.db_user}:"
            f"{environment_variables.db_password}@{environment_variables.db_host}:"
            f"{environment_variables.db_port}/{environment_variables.db_name}"
        )
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    @contextmanager
    def get_session(self) -> Session:
        db = self.SessionLocal()
        logger.debug("DB session created")
        try:
            yield db
        finally:
            db.close()
            logger.debug("DB session closed")
