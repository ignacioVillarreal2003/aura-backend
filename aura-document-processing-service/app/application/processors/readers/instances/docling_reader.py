import logging
from pathlib import Path
from typing import Any
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import AcceleratorDevice, AcceleratorOptions, PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

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

_DOCLING_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp",
})


class DoclingReader(BaseReader):
    def __init__(
            self,
            reader_settings: ReaderSettings,
    ) -> None:
        self._settings = reader_settings

        try:
            device_map = {
                "cuda": AcceleratorDevice.CUDA,
                "mps": AcceleratorDevice.MPS,
                "auto": AcceleratorDevice.AUTO,
                "cpu": AcceleratorDevice.CPU,
            }
            device = device_map.get(
                reader_settings.docling_device.lower(),
                AcceleratorDevice.CPU,
            )

            pipeline_options = PdfPipelineOptions()
            pipeline_options.accelerator_options = AcceleratorOptions(
                num_threads=reader_settings.docling_num_threads,
                device=device,
            )

            if reader_settings.docling_artifacts_path:
                pipeline_options.artifacts_path = reader_settings.docling_artifacts_path

            self._converter = DocumentConverter(
                allowed_formats=[
                    InputFormat.PDF,
                    InputFormat.DOCX,
                    InputFormat.PPTX,
                    InputFormat.XLSX,
                    InputFormat.IMAGE,
                ],
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
                },
            )

            logger.info(
                "The Docling reader was initialized successfully.",
                extra={
                    "device": reader_settings.docling_device,
                    "num_threads": reader_settings.docling_num_threads,
                    "supported_extensions": sorted(_DOCLING_SUPPORTED_EXTENSIONS),
                },
            )
        except Exception as e:
            logger.exception("Failed to initialize the Docling reader.")
            raise DoclingInitializationException("Failed to initialize the Docling reader.") from e

    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in _DOCLING_SUPPORTED_EXTENSIONS

    def read(self, file_path: Path) -> str:
        self._validate_file_exists(file_path)

        if not self.can_handle(file_path):
            raise UnsupportedDoclingFormatException(
                "This file format is not supported by the Docling reader."
            )

        logger.info(
            "Reading the file with Docling.",
            extra={
                "file_name": file_path.name,
                "format": file_path.suffix.lower(),
            },
        )

        try:
            result = self._converter.convert(str(file_path))
            document = getattr(result, "document", None)

            if document is None:
                raise DoclingReadException("Docling returned no document after conversion.")

            text = self._export_plain_text(document)

            if not text:
                raise DoclingExtractionException(
                    "Docling finished conversion but produced no extractable text."
                )

            logger.info(
                "The file was read successfully with Docling.",
                extra={
                    "file_name": file_path.name,
                    "chars": len(text),
                },
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
                "Failed to read the file with Docling.",
                extra={"file_name": file_path.name},
            )
            raise DoclingReadException(
                "An unexpected error occurred while processing the file with Docling."
            ) from e

    @staticmethod
    def _export_plain_text(document: Any) -> str:
        if hasattr(document, "export_to_text"):
            return (document.export_to_text() or "").strip()
        return (document.export_to_markdown() or "").strip()
