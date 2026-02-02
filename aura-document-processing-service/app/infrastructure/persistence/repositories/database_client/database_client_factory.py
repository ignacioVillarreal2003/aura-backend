import logging
from typing import Optional
from asyncio import Lock

from app.infrastructure.persistence.repositories.database_client.database_client import DatabaseClient

logger = logging.getLogger(__name__)

_global_database_client: Optional[DatabaseClient] = None
_global_database_client_lock = Lock()


async def get_global_database_client(
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
) -> DatabaseClient:
    global _global_database_client

    async with _global_database_client_lock:
        if _global_database_client is None:
            logger.info("Creating global DatabaseClient singleton")

            _global_database_client = DatabaseClient.create(
                db_driver=db_driver,
                db_user=db_user,
                db_password=db_password,
                db_host=db_host,
                db_port=db_port,
                db_name=db_name,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_recycle=pool_recycle,
                pool_pre_ping=pool_pre_ping,
                echo=echo,
                pool_timeout=pool_timeout,
                connect_timeout=connect_timeout
            )

            await _global_database_client.start()
            logger.info("Global DatabaseClient started successfully")

        else:
            logger.debug("Returning existing global DatabaseClient")

    return _global_database_client


async def shutdown_global_database_client() -> None:
    global _global_database_client

    async with _global_database_client_lock:
        if _global_database_client is not None:
            logger.info("Shutting down global DatabaseClient")
            await _global_database_client.stop()
            _global_database_client = None
            logger.info("Global DatabaseClient shut down successfully")
        else:
            logger.debug("Global DatabaseClient already shut down")
