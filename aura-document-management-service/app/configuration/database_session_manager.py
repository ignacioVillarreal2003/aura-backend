import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.configuration.environment_variables import environment_variables


logger = logging.getLogger(__name__)


class DatabaseSessionManager:
    def __init__(self):
        DATABASE_URL = (
            f"{environment_variables.db_driver}://{environment_variables.db_user}:{environment_variables.db_password}"
            f"@{environment_variables.db_host}:{environment_variables.db_port}/{environment_variables.db_name}"
        )
        self.engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def get_db_session(self):
        db = self.SessionLocal()
        logger.debug("DB session created")
        try:
            yield db
        finally:
            db.close()
            logger.debug("DB session closed")