import logging
from typing import Optional

from app.infrastructure.persistence.database.database_manager.database_manager import (
    DatabaseManager
)
from app.infrastructure.persistence.database.database_manager.database_manager_settings import DatabaseManagerSettings
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import (
    DatabaseManagerInterface
)

logger = logging.getLogger(__name__)


def create_database_manager(
        user: Optional[str],
        password: Optional[str],
        host: Optional[str],
        port: Optional[int],
        name: Optional[str],
        database_manager_settings: Optional[DatabaseManagerSettings] = None,
        **config_kwargs
) -> DatabaseManagerInterface:
    try:
        logger.info("Creating DatabaseManager instance")

        if database_manager_settings is None:
            if user and password and host and port and name:
                database_manager_settings = DatabaseManagerSettings(
                    user=user,
                    password=password,
                    host=host,
                    port=port,
                    name=name,
                    **config_kwargs
                )
            else:
                database_manager_settings = DatabaseManagerSettings(
                    **config_kwargs
                )
        return DatabaseManager(
            database_manager_settings=database_manager_settings
        )

    except Exception as e:
        logger.exception("Failed to create DatabaseManager")
        raise
