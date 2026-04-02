import logging
from pathlib import Path

from app.application.processors.readers.exceptions.reader_exception import (
    DoclingExtractionException,
    DoclingInitializationException,
    DoclingReadException,
    ReaderFileNotFoundException,
    UnsupportedDoclingFormatException,
)
from app.application.processors.readers.instances.base_reader import BaseReader
from app.application.processors.readers.reader_settings import ReaderSettings

logger = logging.getLogger(__name__)

_SUPPORTED_SUFFIXES = frozenset({".pdf", ".docx"})
_PDF_MAGIC = b"%PDF"
_DOCX_MAGIC = b"PK\x03\x04"


class DoclingReader(BaseReader):
    def __init__(self, reader_settings: ReaderSettings) -> None:
        self._settings = reader_settings

        try:
            from docling.document_converter import DocumentConverter
        except ImportError as e:
            logger.exception("Docling is not installed or cannot be imported")
            raise DoclingInitializationException(
                "DoclingReader requires the 'docling' package. "
                "Install it and ensure project requirements include docling."
            ) from e

        try:
            self._converter = DocumentConverter()
            logger.info(
                "DoclingReader initialized successfully",
                extra={"supported_formats": list(_SUPPORTED_SUFFIXES)},
            )
        except Exception as e:
            logger.exception("Failed to initialize DoclingReader")
            raise DoclingInitializationException(
                f"DoclingReader initialization failed: {e}"
            ) from e

    def can_handle(self, file_path: Path) -> bool:
        suffix = file_path.suffix.lower()

        if suffix not in _SUPPORTED_SUFFIXES:
            return False

        if suffix == ".pdf":
            return self._check_magic_bytes(file_path, _PDF_MAGIC, 5)

        if suffix == ".docx":
            return self._check_magic_bytes(file_path, _DOCX_MAGIC, 4)

        return False

    def read(self, file_path: Path) -> str:
        self._validate_file_exists(file_path)
        self._validate_file_size(file_path)

        if not self.can_handle(file_path):
            raise UnsupportedDoclingFormatException(
                f"DoclingReader does not support this file format: {file_path.suffix}"
            )

        logger.info(
            "Reading file with Docling",
            extra={"file": file_path.name, "format": file_path.suffix.lower()},
        )

        try:
            result = self._converter.convert(str(file_path))
            document = getattr(result, "document", None)

            if document is None:
                raise DoclingReadException(
                    "Docling conversion returned no document payload."
                )

            if not hasattr(document, "export_to_markdown"):
                raise DoclingReadException(
                    "Docling document does not support export_to_markdown."
                )

            markdown = document.export_to_markdown()
            text = (markdown or "").strip()

            if not text:
                raise DoclingExtractionException(
                    "Docling completed but no extractable text was produced from the file."
                )

            logger.info(
                "File read successfully with Docling",
                extra={"file": file_path.name, "chars": len(text)},
            )
            return text

        except (
                ReaderFileNotFoundException,
                UnsupportedDoclingFormatException,
                DoclingExtractionException,
                DoclingReadException,
        ):
            raise
        except Exception as e:
            logger.exception(
                "Failed to read file with Docling",
                extra={"file": str(file_path)},
            )
            raise DoclingReadException(
                "An unexpected error occurred while processing the file with Docling."
            ) from e
