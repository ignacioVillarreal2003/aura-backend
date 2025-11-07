from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging

from app.configuration.environment_variables import environment_variables


DATABASE_URL = (
    f"{environment_variables.db_driver}://{environment_variables.db_user}:{environment_variables.db_password}"
    f"@{environment_variables.db_host}:{environment_variables.db_port}/{environment_variables.db_name}"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db_session():
    logger = logging.getLogger(__name__)
    db = SessionLocal()
    logger.debug("DB session created")
    try:
        yield db
    finally:
        db.close()
        logger.debug("DB session closed")
