import logging
from typing import AsyncGenerator
from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.database.database_manager.database_manager import (
    DatabaseManager,
)
from app.infrastructure.persistence.database.database_manager.exceptions.database_manager_exception import (
    DatabaseNotInitializedException
)

logger = logging.getLogger(__name__)


async def get_database_manager(
        request: Request
) -> DatabaseManager:
    try:
        db_manager: DatabaseManager = request.app.state.db_manager

        if not db_manager.is_initialized:
            logger.error("DatabaseManager found but not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available",
            )

        return db_manager

    except AttributeError:
        logger.error("DatabaseManager not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not configured",
        )


async def get_database_session(
        request: Request
) -> AsyncGenerator[AsyncSession, None]:
    db_manager = await get_db_manager(request)

    try:
        async with db_manager.session() as session:
            yield session

    except DatabaseNotInitializedException as e:
        logger.error(f"Database session error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    except Exception as e:
        logger.exception("Unexpected error in database session")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred",
        )


async def get_database_session_read_only(
        request: Request
) -> AsyncGenerator[AsyncSession, None]:
    db_manager = await get_db_manager(request)

    try:
        async with db_manager.session() as session:
            await session.execute("SET TRANSACTION READ ONLY")
            yield session

    except DatabaseNotInitializedException as e:
        logger.error(f"Database session error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    except Exception as e:
        logger.exception("Unexpected error in read-only database session")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred",
        )
