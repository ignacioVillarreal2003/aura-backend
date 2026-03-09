import logging
from fastapi import HTTPException, Request, status

from app.application.processors.text_cleaners.instances.simple_text_cleaner import SimpleTextCleaner
from app.application.processors.text_cleaners.constants.text_cleaner_type import TextCleanerType
from app.application.processors.text_cleaners.exceptions.text_cleaner_exception import (
    UnsupportedTextCleanerTypeException,
    TextCleanerInitializationException
)
from app.application.processors.text_cleaners.interfaces.text_cleaner_interface import TextCleanerInterface

logger = logging.getLogger(__name__)


class TextCleanerFactory:
    def __init__(
            self
    ) -> None:
        self._text_cleaner_classes: dict[TextCleanerType, type[TextCleanerInterface]] = {
            TextCleanerType.simple: SimpleTextCleaner
        }
        self._text_cleaner_cache: dict[TextCleanerType, TextCleanerInterface] = {}
        self._initialize_text_cleaners()

    def get_text_cleaner(
            self,
            text_cleaner_type: TextCleanerType
    ) -> TextCleanerInterface:
        if text_cleaner_type not in self._text_cleaner_classes:
            logger.error(
                "Unsupported text cleaner type",
                extra={
                    "text_cleaner_type": text_cleaner_type
                }
            )
            raise UnsupportedTextCleanerTypeException(f"Unsupported text cleaner type: {text_cleaner_type}")

        if text_cleaner_type not in self._text_cleaner_cache:
            logger.warning(
                "Text cleaner not in cache — retrying initialization",
                extra={
                    "text_cleaner_type": text_cleaner_type
                }
            )
            try:
                text_cleaner_class = self._text_cleaner_classes[text_cleaner_type]
                text_cleaner = text_cleaner_class()
                self._text_cleaner_cache[text_cleaner_type] = text_cleaner
            except Exception as e:
                logger.error(
                    "Text cleaner retry initialization failed",
                    extra={
                        "text_cleaner_type": text_cleaner_type,
                        "error": str(e)
                    }
                )
                raise TextCleanerInitializationException(
                    f"Failed to initialize text cleaner: {text_cleaner_type}"
                ) from e

        logger.debug(
            "Returning text cleaner from cache",
            extra={
                "text_cleaner_type": text_cleaner_type
            }
        )

        return self._text_cleaner_cache[text_cleaner_type]

    def is_supported(
            self,
            text_cleaner_type: TextCleanerType
    ) -> bool:
        return text_cleaner_type in self._text_cleaner_classes

    def get_supported_types(
            self
    ) -> list[TextCleanerType]:
        return list(self._text_cleaner_classes.keys())

    def _initialize_text_cleaners(
            self
    ) -> None:
        for text_cleaner_type, text_cleaner_class in self._text_cleaner_classes.items():
            try:
                logger.debug(
                    "Initializing text cleaner",
                    extra={
                        "text_cleaner_type": text_cleaner_type
                    }
                )
                text_cleaner = text_cleaner_class()
                self._text_cleaner_cache[text_cleaner_type] = text_cleaner
                logger.debug(
                    "Text cleaner initialized successfully",
                    extra={
                        "text_cleaner_type": text_cleaner_type
                    }
                )
            except Exception as e:
                logger.error(
                    "Failed to initialize text cleaner — will retry on first use",
                    extra={
                        "text_cleaner_type": text_cleaner_type,
                        "error": str(e)
                    }
                )


async def get_text_cleaner_factory(
        request: Request
) -> TextCleanerFactory:
    try:
        text_cleaner_factory: TextCleanerFactory = request.app.state.text_cleaner_factory
        return text_cleaner_factory
    except AttributeError:
        logger.error("TextCleanerFactory not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Text cleaner factory not configured"
        )
