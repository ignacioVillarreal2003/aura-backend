"""Unit tests for CreateDocumentServiceUtils."""

import io

import pytest
from starlette.datastructures import Headers, UploadFile

from app.application.services.document.create_document_service.create_document_service_settings import (
    CreateDocumentServiceSettings,
)
from app.application.services.document.create_document_service.create_document_service_utils import (
    CreateDocumentServiceUtils,
)
from app.domain.constants.document.document_mime_type import DocumentMimeType
from tests.constants import CT_DOCX, CT_PDF, PDF_MINIMAL


def _upload(data: bytes, filename: str, content_type: str) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(data),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def test_get_document_mime_type_pdf() -> None:
    utils = CreateDocumentServiceUtils(CreateDocumentServiceSettings())
    uf = _upload(PDF_MINIMAL, "a.pdf", CT_PDF)
    assert utils.get_document_mime_type(uf) == DocumentMimeType.pdf


def test_get_document_mime_type_docx() -> None:
    utils = CreateDocumentServiceUtils(CreateDocumentServiceSettings())
    docx_bytes = b"PK\x03\x04" + b"\x00" * 10
    uf = _upload(docx_bytes, "a.docx", CT_DOCX)
    assert utils.get_document_mime_type(uf) == DocumentMimeType.docx


@pytest.mark.asyncio
async def test_compute_file_hash_stable() -> None:
    utils = CreateDocumentServiceUtils(CreateDocumentServiceSettings())
    uf = _upload(b"hello", "x.txt", "text/plain")
    h1 = await utils.compute_file_hash(uf)
    h2 = await utils.compute_file_hash(uf)
    assert h1 == h2
    assert len(h1) == 64
