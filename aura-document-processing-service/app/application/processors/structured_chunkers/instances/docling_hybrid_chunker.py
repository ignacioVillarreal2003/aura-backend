import logging
from pathlib import Path
from typing import Any, Optional

from app.application.processors.structured_chunkers.dtos.document_chunk import DocumentChunk
from app.application.processors.structured_chunkers.exceptions.structured_chunker_exception import (
    StructuredChunkerExecutionException,
    StructuredChunkerInitializationException,
    StructuredChunkerUnavailableException,
)
from app.application.processors.structured_chunkers.interfaces.structured_chunker_interface import (
    StructuredChunkerInterface,
)
from app.application.processors.structured_chunkers.structured_chunker_settings import (
    StructuredChunkerSettings,
)

logger = logging.getLogger(__name__)

_DOCLING_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp",
})


class DoclingHybridChunker(StructuredChunkerInterface):
    """Structure-aware chunker backed by Docling's HybridChunker.

    Converts a document to a ``DoclingDocument`` and chunks it hierarchically and
    token-aware, so headings, tables and list items are kept intact rather than
    sliced by a flat-text window. Each emitted chunk carries structural metadata
    (page, heading path, bounding box, char span) resolved from Docling provenance.

    Docling is an optional, heavy dependency; all Docling imports are performed
    lazily at construction so this module can be imported without it installed.
    """

    def __init__(self, settings: Optional[StructuredChunkerSettings] = None) -> None:
        self._settings = settings or StructuredChunkerSettings()
        try:
            self._converter = self._build_converter()
            self._chunker = self._build_chunker()
        except StructuredChunkerUnavailableException:
            raise
        except Exception as e:
            logger.exception("Failed to initialize the Docling hybrid chunker.")
            raise StructuredChunkerInitializationException(
                "Failed to initialize the Docling hybrid chunker."
            ) from e

        logger.info(
            "The Docling hybrid chunker was initialized successfully.",
            extra={
                "tokenizer_model": self._settings.tokenizer_model,
                "max_tokens": self._settings.max_tokens,
                "merge_peers": self._settings.merge_peers,
                "device": self._settings.device,
            },
        )

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in _DOCLING_SUPPORTED_EXTENSIONS

    def get_chunk_params(self) -> tuple[int | None, int | None]:
        # HybridChunker is token-bounded and merges peers; it does not use a fixed
        # overlap window, so overlap is reported as 0.
        return self._settings.max_tokens, 0

    def chunk_file(self, file_path: Path) -> list[DocumentChunk]:
        if not file_path.exists():
            raise StructuredChunkerExecutionException("The file to chunk was not found.")
        if not self.supports(file_path):
            raise StructuredChunkerExecutionException(
                "This file format is not supported by the Docling hybrid chunker."
            )

        try:
            result = self._converter.convert(str(file_path))
            document = getattr(result, "document", None)
            if document is None:
                raise StructuredChunkerExecutionException(
                    "Docling returned no document after conversion."
                )

            chunks: list[DocumentChunk] = []
            for raw_chunk in self._chunker.chunk(dl_doc=document):
                text = (getattr(raw_chunk, "text", "") or "").strip()
                if not text:
                    continue
                embed_text = self._contextualize(raw_chunk, fallback=text)
                chunks.append(self._to_document_chunk(raw_chunk, text, embed_text))

            if not chunks:
                raise StructuredChunkerExecutionException(
                    "Docling produced no chunks for the document."
                )

            logger.info(
                "The document was chunked structurally with Docling.",
                extra={"file_name": file_path.name, "chunk_count": len(chunks)},
            )
            return chunks

        except StructuredChunkerExecutionException:
            raise
        except Exception as e:
            logger.exception(
                "Failed to chunk the document with Docling.",
                extra={"file_name": file_path.name},
            )
            raise StructuredChunkerExecutionException(
                "An unexpected error occurred while chunking the document with Docling."
            ) from e

    def _build_converter(self) -> Any:
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import (
                AcceleratorDevice,
                AcceleratorOptions,
                PdfPipelineOptions,
            )
            from docling.document_converter import DocumentConverter, PdfFormatOption
        except ImportError as e:
            raise StructuredChunkerUnavailableException(
                "Docling is not installed; the Docling hybrid chunker is unavailable."
            ) from e

        device_map = {
            "cuda": AcceleratorDevice.CUDA,
            "mps": AcceleratorDevice.MPS,
            "auto": AcceleratorDevice.AUTO,
            "cpu": AcceleratorDevice.CPU,
        }
        device = device_map.get(self._settings.device.lower(), AcceleratorDevice.AUTO)

        pipeline_options = PdfPipelineOptions()
        pipeline_options.accelerator_options = AcceleratorOptions(
            num_threads=self._settings.num_threads,
            device=device,
        )

        return DocumentConverter(
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

    def _build_chunker(self) -> Any:
        try:
            from docling.chunking import HybridChunker
        except ImportError as e:
            raise StructuredChunkerUnavailableException(
                "Docling chunking is not installed; the Docling hybrid chunker is unavailable."
            ) from e

        # Prefer the modern tokenizer abstraction (docling-core >= 2.x); fall back
        # to the legacy string form for older 2.x releases.
        try:
            from docling_core.transforms.chunker.tokenizer.huggingface import (
                HuggingFaceTokenizer,
            )
            from transformers import AutoTokenizer

            tokenizer = HuggingFaceTokenizer(
                tokenizer=AutoTokenizer.from_pretrained(self._settings.tokenizer_model),
                max_tokens=self._settings.max_tokens,
            )
            return HybridChunker(tokenizer=tokenizer, merge_peers=self._settings.merge_peers)
        except ImportError:
            return HybridChunker(
                tokenizer=self._settings.tokenizer_model,
                max_tokens=self._settings.max_tokens,
                merge_peers=self._settings.merge_peers,
            )

    def _contextualize(self, raw_chunk: Any, fallback: str) -> str:
        # HybridChunker.contextualize() prepends the heading path / captions to the
        # chunk's serialized text. Used only as the embedding input so a chunk keeps
        # its section anchor in the vector even when a concept is split at a border.
        # Best-effort: any failure degrades to the raw chunk text.
        try:
            enriched = (self._chunker.contextualize(chunk=raw_chunk) or "").strip()
        except Exception:
            logger.warning(
                "Failed to contextualize a Docling chunk; using raw text for embedding.",
                exc_info=True,
            )
            return fallback
        return enriched or fallback

    def _to_document_chunk(self, raw_chunk: Any, text: str, embed_text: str) -> DocumentChunk:
        headings = self._extract_headings(raw_chunk)
        page_number, char_span, bbox = self._extract_provenance(raw_chunk)

        return DocumentChunk(
            text=text,
            embed_text=embed_text,
            page_number=page_number,
            section_path=" > ".join(headings) if headings else None,
            heading=headings[-1] if headings else None,
            char_start=char_span[0] if char_span else None,
            char_end=char_span[1] if char_span else None,
            bbox=bbox,
        )

    @staticmethod
    def _extract_headings(raw_chunk: Any) -> list[str]:
        meta = getattr(raw_chunk, "meta", None)
        headings = getattr(meta, "headings", None) if meta is not None else None
        if not headings:
            return []
        return [str(h).strip() for h in headings if str(h).strip()]

    @staticmethod
    def _extract_provenance(
            raw_chunk: Any,
    ) -> tuple[Optional[int], Optional[tuple[int, int]], Optional[dict]]:
        meta = getattr(raw_chunk, "meta", None)
        doc_items = getattr(meta, "doc_items", None) if meta is not None else None
        if not doc_items:
            return None, None, None

        page_number: Optional[int] = None
        char_span: Optional[tuple[int, int]] = None
        bbox: Optional[dict] = None

        for item in doc_items:
            for prov in getattr(item, "prov", None) or []:
                page_no = getattr(prov, "page_no", None)
                if page_no is not None:
                    page_number = page_no if page_number is None else min(page_number, page_no)

                if char_span is None:
                    span = getattr(prov, "charspan", None)
                    if span and len(span) == 2:
                        char_span = (int(span[0]), int(span[1]))

                if bbox is None:
                    box = getattr(prov, "bbox", None)
                    if box is not None:
                        bbox = {
                            "page": page_no,
                            "l": getattr(box, "l", None),
                            "t": getattr(box, "t", None),
                            "r": getattr(box, "r", None),
                            "b": getattr(box, "b", None),
                            "coord_origin": str(getattr(box, "coord_origin", "") or "") or None,
                        }

        return page_number, char_span, bbox
