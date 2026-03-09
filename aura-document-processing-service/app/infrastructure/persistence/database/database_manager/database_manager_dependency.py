import logging
from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.database.database_manager.exceptions.database_manager_exception import (
    DatabaseNotInitializedException,
    DatabaseSessionException
)
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import (
    DatabaseManagerInterface
)

logger = logging.getLogger(__name__)


async def get_database_manager(request: Request) -> DatabaseManagerInterface:
    try:
        database_manager: DatabaseManagerInterface = request.app.state.db_manager
        if not database_manager.is_initialized:
            logger.error("DatabaseManager found in app state but not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available"
            )
        return database_manager
    except AttributeError:
        logger.error("DatabaseManager not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DatabaseManager not configured"
        )


async def get_database_session(request: Request) -> AsyncSession:
    database_manager = await get_database_manager(request)
    try:
        async with database_manager.session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    except HTTPException:
        raise
    except DatabaseNotInitializedException:
        logger.error("Database session requested but manager is not initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    except DatabaseSessionException:
        logger.exception("Database session error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
