import logging
from pathlib import Path

from app.application.processors.readers.exceptions.reader_exception import (
    DoclingExtractionException,
    DoclingInitializationException,
    DoclingReadException,
    ReaderFileNotFoundException,
    UnsupportedDoclingFormatException
)
from app.application.processors.readers.instances.base_reader import BaseReader
from app.application.processors.readers.reader_settings import ReaderSettings

logger = logging.getLogger(__name__)

_SUPPORTED_SUFFIXES = frozenset({".pdf", ".docx"})
_PDF_MAGIC = b"%PDF"
_DOCX_MAGIC = b"PK\x03\x04"


class DoclingReader(BaseReader):
    def __init__(
            self,
            reader_settings: ReaderSettings
    ) -> None:
        self._settings = reader_settings

        try:
            from docling.document_converter import DocumentConverter
        except ImportError as e:
            logger.exception("Docling is not installed or could not be imported.", )
            raise DoclingInitializationException("The Docling reader needs the docling package installed.") from e

        try:
            self._converter = DocumentConverter()
            logger.info(
                "The Docling reader was initialized successfully.",
                extra={
                    "supported_formats": list(_SUPPORTED_SUFFIXES)
                }
            )
        except Exception as e:
            logger.exception("Failed to initialize the Docling reader.")
            raise DoclingInitializationException("Failed to initialize the Docling reader.") from e

    def can_handle(
            self,
            file_path: Path
    ) -> bool:
        suffix = file_path.suffix.lower()

        if suffix not in _SUPPORTED_SUFFIXES:
            return False

        if suffix == ".pdf":
            return self._check_magic_bytes(file_path, _PDF_MAGIC, 5)

        if suffix == ".docx":
            return self._check_magic_bytes(file_path, _DOCX_MAGIC, 4)

        return False

    def read(
            self,
            file_path: Path
    ) -> str:
        self._validate_file_exists(file_path)
        self._validate_file_size(file_path)

        if not self.can_handle(file_path):
            raise UnsupportedDoclingFormatException("This file format is not supported by the Docling reader.")

        logger.info(
            "Reading the file with Docling.",
            extra={
                "file_name": file_path.name,
                "format": file_path.suffix.lower()
            }
        )

        try:
            result = self._converter.convert(str(file_path))
            document = getattr(result, "document", None)

            if document is None:
                raise DoclingReadException("Docling returned no document after conversion.")

            if not hasattr(document, "export_to_markdown"):
                raise DoclingReadException("The Docling document cannot be exported to Markdown.")

            markdown = document.export_to_markdown()
            text = (markdown or "").strip()

            if not text:
                raise DoclingExtractionException("Docling finished but produced no extractable text.")

            logger.info(
                "The file was read successfully with Docling.",
                extra={
                    "file_name": file_path.name,
                    "chars": len(text)
                }
            )
            return text

        except (
                ReaderFileNotFoundException,
                UnsupportedDoclingFormatException,
                DoclingExtractionException,
                DoclingReadException
        ):
            raise
        except Exception as e:
            logger.exception(
                "Failed to read the file with Docling.",
                extra={
                    "file_name": file_path.name
                }
            )
            raise DoclingReadException("An unexpected error occurred while processing the file with Docling.") from e
