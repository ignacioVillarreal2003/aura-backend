from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.configuration.environment_variables import environment_variables
import logging
from contextlib import contextmanager


DATABASE_URL = (
    f"{environment_variables.db_driver}://{environment_variables.db_user}:{environment_variables.db_password}"
    f"@{environment_variables.db_host}:{environment_variables.db_port}/{environment_variables.db_name}"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

logger = logging.getLogger(__name__)

# ✅ Versión para FastAPI (usada con Depends)
def get_db_session():
    db = SessionLocal()
    logger.debug("DB session created (FastAPI context)")
    try:
        yield db
    finally:
        db.close()
        logger.debug("DB session closed (FastAPI context)")


@contextmanager
def get_sync_db():
    db = SessionLocal()
    logger.debug("DB session created (sync context)")
    try:
        yield db
    finally:
        db.close()
        logger.debug("DB session closed (sync context)")
