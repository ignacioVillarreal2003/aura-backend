import logging
from typing import Optional
from fastapi import HTTPException, Request, status

from app.application.processors.embedders.instances.ollama_embedder import OllamaEmbedder
from app.application.processors.embedders.constants.embedder_type import EmbedderType
from app.application.processors.embedders.embedder_settings import EmbedderSettings
from app.application.processors.embedders.exceptions.embedder_exception import (
    UnsupportedEmbedderTypeException,
    EmbedderInitializationException
)
from app.application.processors.embedders.interfaces.embedder_interface import EmbedderInterface

logger = logging.getLogger(__name__)


class EmbedderFactory:
    def __init__(
            self,
            embedder_settings: Optional[EmbedderSettings] = None
    ) -> None:
        self._embedder_settings = embedder_settings or EmbedderSettings()

        self._embedder_classes: dict[EmbedderType, type[EmbedderInterface]] = {
            EmbedderType.ollama: OllamaEmbedder
        }
        self._embedder_cache: dict[EmbedderType, EmbedderInterface] = {}
        self._initialize_embedders()

    def get_embedder(
            self,
            embedder_type: EmbedderType
    ) -> EmbedderInterface:
        if embedder_type not in self._embedder_classes:
            logger.error(
                "Unsupported embedder type",
                extra={
                    "embedder_type": embedder_type
                }
            )
            raise UnsupportedEmbedderTypeException(f"Unsupported embedder type: {embedder_type}")

        if embedder_type not in self._embedder_cache:
            logger.warning(
                "Embedder not in cache — retrying initialization",
                extra={
                    "embedder_type": embedder_type
                }
            )
            try:
                embedder_class = self._embedder_classes[embedder_type]
                embedder = embedder_class(
                    embedder_settings=self._embedder_settings
                )
                self._embedder_cache[embedder_type] = embedder
            except Exception as e:
                logger.error(
                    "Embedder retry initialization failed",
                    extra={
                        "embedder_type": embedder_type,
                        "error": str(e)
                    }
                )
                raise EmbedderInitializationException(f"Failed to initialize embedder: {embedder_type}") from e

        logger.debug(
            "Returning embedder from cache",
            extra={
                "embedder_type": embedder_type
            }
        )

        return self._embedder_cache[embedder_type]

    def is_supported(
            self,
            embedder_type: EmbedderType
    ) -> bool:
        return embedder_type in self._embedder_classes

    def get_embedder_classes(
            self
    ) -> list[EmbedderType]:
        return list(self._embedder_classes.keys())

    def _initialize_embedders(
            self
    ) -> None:
        for embedder_type, embedder_class in self._embedder_classes.items():
            try:
                logger.debug(
                    "Initializing embedder",
                    extra={
                        "embedder_type": embedder_type
                    }
                )
                embedder = embedder_class(
                    embedder_settings=self._embedder_settings
                )
                self._embedder_cache[embedder_type] = embedder
                logger.debug(
                    "Embedder initialized successfully",
                    extra={
                        "embedder_type": embedder_type
                    }
                )
            except Exception as e:
                logger.error(
                    "Failed to initialize embedder — will retry on first use",
                    extra={
                        "embedder_type": embedder_type,
                        "error": str(e)
                    }
                )


async def get_embedder_factory(
        request: Request
) -> EmbedderFactory:
    try:
        embedder_factory: EmbedderFactory = request.app.state.embedder_factory
        return embedder_factory
    except AttributeError:
        logger.error("EmbedderFactory not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedder factory not configured"
        )
