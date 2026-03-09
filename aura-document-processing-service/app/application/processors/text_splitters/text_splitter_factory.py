import logging
from typing import Optional
from fastapi import HTTPException, Request, status

from app.application.processors.text_splitters.instances.recursive_text_splitter import RecursiveTextSplitter
from app.application.processors.text_splitters.constants.text_splitter_type import TextSplitterType
from app.application.processors.text_splitters.exceptions.text_splitter_exception import (
    UnsupportedTextSplitterTypeException,
    TextSplitterInitializationException
)
from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface
from app.application.processors.text_splitters.text_splitter_settings import TextSplitterSettings

logger = logging.getLogger(__name__)


class TextSplitterFactory:
    def __init__(
            self,
            text_splitter_settings: Optional[TextSplitterSettings] = None
    ) -> None:
        self._text_splitter_settings = text_splitter_settings or TextSplitterSettings()

        self._text_splitter_classes: dict[TextSplitterType, type[TextSplitterInterface]] = {
            TextSplitterType.recursive: RecursiveTextSplitter
        }
        self._text_splitter_cache: dict[TextSplitterType, TextSplitterInterface] = {}
        self._initialize_text_splitters()

    def get_text_splitter(
            self,
            text_splitter_type: TextSplitterType
    ) -> TextSplitterInterface:
        if text_splitter_type not in self._text_splitter_classes:
            logger.error(
                "Unsupported text splitter type",
                extra={
                    "text_splitter_type": text_splitter_type
                }
            )
            raise UnsupportedTextSplitterTypeException(f"Unsupported text splitter type: {text_splitter_type}")

        if text_splitter_type not in self._text_splitter_cache:
            logger.warning(
                "Text splitter not in cache — retrying initialization",
                extra={
                    "text_splitter_type": text_splitter_type
                }
            )
            try:
                text_splitter_class = self._text_splitter_classes[text_splitter_type]
                text_splitter = text_splitter_class(
                    text_splitter_settings=self._text_splitter_settings
                )
                self._text_splitter_cache[text_splitter_type] = text_splitter
            except Exception as e:
                logger.error(
                    "Text splitter retry initialization failed",
                    extra={
                        "text_splitter_type": text_splitter_type,
                        "error": str(e)
                    }
                )
                raise TextSplitterInitializationException(
                    f"Failed to initialize text splitter: {text_splitter_type}"
                ) from e

        logger.debug(
            "Returning text splitter from cache",
            extra={
                "text_splitter_type": text_splitter_type
            }
        )

        return self._text_splitter_cache[text_splitter_type]

    def is_supported(
            self,
            text_splitter_type: TextSplitterType
    ) -> bool:
        return text_splitter_type in self._text_splitter_classes

    def get_supported_types(
            self
    ) -> list[TextSplitterType]:
        return list(self._text_splitter_classes.keys())

    def get_settings(
            self
    ) -> TextSplitterSettings:
        return self._text_splitter_settings

    def _initialize_text_splitters(
            self
    ) -> None:
        for text_splitter_type, text_splitter_class in self._text_splitter_classes.items():
            try:
                logger.debug(
                    "Initializing text splitter",
                    extra={
                        "text_splitter_type": text_splitter_type
                    }
                )
                text_splitter = text_splitter_class(
                    text_splitter_settings=self._text_splitter_settings
                )
                self._text_splitter_cache[text_splitter_type] = text_splitter
                logger.debug(
                    "Text splitter initialized successfully",
                    extra={
                        "text_splitter_type": text_splitter_type
                    }
                )
            except Exception as e:
                logger.error(
                    "Failed to initialize text splitter — will retry on first use",
                    extra={
                        "text_splitter_type": text_splitter_type,
                        "error": str(e)
                    }
                )


async def get_text_splitter_factory(
        request: Request
) -> TextSplitterFactory:
    try:
        text_splitter_factory: TextSplitterFactory = request.app.state.text_splitter_factory
        return text_splitter_factory
    except AttributeError:
        logger.error("TextSplitterFactory not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Text splitter factory not configured"
        )
