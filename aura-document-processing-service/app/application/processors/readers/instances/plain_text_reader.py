import logging
import re
from pathlib import Path
from typing import Optional

from app.application.processors.readers.exceptions.reader_exception import (
    PlainTextHasNoContentException,
    PlainTextReadException,
    ReaderFileNotFoundException,
)
from app.application.processors.readers.instances.base_reader import BaseReader
from app.application.processors.readers.reader_settings import ReaderSettings

logger = logging.getLogger(__name__)

_PLAIN_TEXT_EXTENSIONS: frozenset[str] = frozenset({".txt", ".md"})
_DECODE_ENCODINGS: tuple[str, ...] = ("utf-8-sig", "utf-8", "latin-1", "cp1252")

_MD_IMAGE_RE = re.compile(r'!\[[^\]]*\]\([^)]*\)')
_MD_LINK_RE = re.compile(r'\[([^\]]+)\]\([^)]*\)')
_MD_CODE_BLOCK_RE = re.compile(r'```[^\n]*\n(.*?)```', re.DOTALL)
_MD_INLINE_CODE_RE = re.compile(r'`([^`\n]+)`')
_MD_BOLD_ITALIC_RE = re.compile(r'(\*{1,3}|_{1,3})(.+?)\1', re.DOTALL)
_MD_HEADING_RE = re.compile(r'^#{1,6}\s+', re.MULTILINE)
_MD_HR_RE = re.compile(r'^\s*[-*_]{3,}\s*$', re.MULTILINE)
_MD_BLOCKQUOTE_RE = re.compile(r'^>\s?', re.MULTILINE)
_MD_LIST_BULLET_RE = re.compile(r'^\s*[-*+]\s+', re.MULTILINE)
_MD_LIST_NUMBERED_RE = re.compile(r'^\s*\d+\.\s+', re.MULTILINE)


class PlainTextReader(BaseReader):
    def __init__(
            self,
            reader_settings: Optional[ReaderSettings] = None,
    ) -> None:
        self._settings = reader_settings or ReaderSettings()
        logger.info("The plain text reader was initialized successfully.")

    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in _PLAIN_TEXT_EXTENSIONS

    def read(self, file_path: Path) -> str:
        self._validate_file_exists(file_path)

        suffix = file_path.suffix.lower()
        logger.info(
            "Reading a plain text file.",
            extra={
                "file_name": file_path.name,
                "format": suffix,
            },
        )

        try:
            raw = file_path.read_bytes()
            text = self._decode(raw)

            if suffix == ".md":
                text = _strip_markdown(text)

            if not text.strip():
                raise PlainTextHasNoContentException(
                    "The file does not contain any readable text content."
                )

            result = text.strip()

            logger.info(
                "The plain text file was read successfully.",
                extra={
                    "file_name": file_path.name,
                    "chars": len(result),
                },
            )
            return result

        except (ReaderFileNotFoundException, PlainTextHasNoContentException):
            raise
        except Exception as e:
            logger.exception(
                "An error occurred while reading the plain text file.",
                extra={"file_name": file_path.name},
            )
            raise PlainTextReadException(
                "An unexpected error occurred while reading the file."
            ) from e

    @staticmethod
    def _decode(raw: bytes) -> str:
        for encoding in _DECODE_ENCODINGS:
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise PlainTextReadException(
            "Could not decode the file with any of the supported encodings "
            f"({', '.join(_DECODE_ENCODINGS)})."
        )


def _strip_markdown(text: str) -> str:
    text = _MD_IMAGE_RE.sub('', text)
    text = _MD_LINK_RE.sub(r'\1', text)
    text = _MD_CODE_BLOCK_RE.sub(r'\1', text)
    text = _MD_INLINE_CODE_RE.sub(r'\1', text)
    text = _MD_BOLD_ITALIC_RE.sub(r'\2', text)
    text = _MD_HEADING_RE.sub('', text)
    text = _MD_HR_RE.sub('', text)
    text = _MD_BLOCKQUOTE_RE.sub('', text)
    text = _MD_LIST_BULLET_RE.sub('', text)
    text = _MD_LIST_NUMBERED_RE.sub('', text)
    return text
