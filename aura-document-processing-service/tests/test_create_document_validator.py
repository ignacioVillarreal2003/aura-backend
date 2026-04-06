"""Unit tests for CreateDocumentServiceValidator (injected settings)."""

import io

import pytest

from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.document.create_document_service.create_document_service_settings import (
    CreateDocumentServiceSettings,
)
from app.application.services.document.create_document_service.create_document_service_validator import (
    CreateDocumentServiceValidator,
)
from app.application.services.document.create_document_service.exceptions.create_document_service_exception import (
    CreateDocumentInvalidException,
    CreateDocumentSizeExceededException,
    CreateDocumentUnsupportedTypeException,
)
from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest
from tests.constants import CT_DOCX, CT_PDF, DOCX_ZIP_PREFIX, PDF_MINIMAL
from tests.conftest import make_upload_file


def _settings(**kwargs) -> CreateDocumentServiceSettings:
    return CreateDocumentServiceSettings(**kwargs)


@pytest.mark.asyncio
async def test_validate_chat_id_non_positive() -> None:
    validator = CreateDocumentServiceValidator(_settings())
    req = CreateDocumentRequest(chat_id=0, prefer_docling=False)
    uf = make_upload_file(data=PDF_MINIMAL, filename="a.pdf", content_type=CT_PDF)
    with pytest.raises(CreateDocumentInvalidException):
        await validator.validate_create_document_request(raw_document=uf, create_document_request=req)


@pytest.mark.asyncio
async def test_validate_filename_empty() -> None:
    validator = CreateDocumentServiceValidator(_settings())
    req = CreateDocumentRequest(chat_id=1, prefer_docling=False)
    uf = make_upload_file(data=PDF_MINIMAL, filename="", content_type=CT_PDF)
    with pytest.raises(RequestValidationException):
        await validator.validate_create_document_request(raw_document=uf, create_document_request=req)


@pytest.mark.parametrize(
    "bad_name",
    ["../x.pdf", "a/b.pdf", "a\\b.pdf", "a\x00b.pdf", "x" * 256 + ".pdf"],
)
@pytest.mark.asyncio
async def test_validate_filename_invalid_chars_or_length(bad_name: str) -> None:
    validator = CreateDocumentServiceValidator(_settings())
    req = CreateDocumentRequest(chat_id=1, prefer_docling=False)
    uf = make_upload_file(data=PDF_MINIMAL, filename=bad_name, content_type=CT_PDF)
    with pytest.raises(CreateDocumentInvalidException):
        await validator.validate_create_document_request(raw_document=uf, create_document_request=req)


class _FakeUploadNoContentType:
    """Minimal upload stand-in with content_type falsy (validator branch)."""

    filename = "a.pdf"
    content_type = None
    file = io.BytesIO(PDF_MINIMAL)


@pytest.mark.asyncio
async def test_validate_content_type_missing() -> None:
    validator = CreateDocumentServiceValidator(_settings())
    req = CreateDocumentRequest(chat_id=1, prefer_docling=False)
    with pytest.raises(CreateDocumentInvalidException):
        await validator.validate_create_document_request(
            raw_document=_FakeUploadNoContentType(),  # type: ignore[arg-type]
            create_document_request=req,
        )


@pytest.mark.asyncio
async def test_validate_content_type_not_allowed() -> None:
    validator = CreateDocumentServiceValidator(_settings())
    req = CreateDocumentRequest(chat_id=1, prefer_docling=False)
    uf = make_upload_file(data=PDF_MINIMAL, filename="a.pdf", content_type="text/plain")
    with pytest.raises(CreateDocumentUnsupportedTypeException):
        await validator.validate_create_document_request(raw_document=uf, create_document_request=req)


@pytest.mark.asyncio
async def test_validate_file_too_small() -> None:
    settings = _settings(min_file_size_bytes=10)
    validator = CreateDocumentServiceValidator(settings)
    req = CreateDocumentRequest(chat_id=1, prefer_docling=False)
    small = b"%PDFxx"
    uf = make_upload_file(data=small, filename="a.pdf", content_type=CT_PDF)
    with pytest.raises(CreateDocumentInvalidException):
        await validator.validate_create_document_request(raw_document=uf, create_document_request=req)


@pytest.mark.asyncio
async def test_validate_file_too_large() -> None:
    settings = _settings(max_file_size_mb=1)
    validator = CreateDocumentServiceValidator(settings)
    req = CreateDocumentRequest(chat_id=1, prefer_docling=False)
    big = PDF_MINIMAL + (b"x" * (2 * 1024 * 1024))
    uf = make_upload_file(data=big, filename="a.pdf", content_type=CT_PDF)
    with pytest.raises(CreateDocumentSizeExceededException):
        await validator.validate_create_document_request(raw_document=uf, create_document_request=req)


@pytest.mark.asyncio
async def test_validate_magic_pdf_mismatch() -> None:
    validator = CreateDocumentServiceValidator(_settings())
    req = CreateDocumentRequest(chat_id=1, prefer_docling=False)
    uf = make_upload_file(data=b"not-a-pdf-at-all", filename="a.pdf", content_type=CT_PDF)
    with pytest.raises(CreateDocumentInvalidException):
        await validator.validate_create_document_request(raw_document=uf, create_document_request=req)


@pytest.mark.asyncio
async def test_validate_magic_docx_ok() -> None:
    validator = CreateDocumentServiceValidator(_settings())
    req = CreateDocumentRequest(chat_id=1, prefer_docling=False)
    uf = make_upload_file(data=DOCX_ZIP_PREFIX, filename="a.docx", content_type=CT_DOCX)
    await validator.validate_create_document_request(raw_document=uf, create_document_request=req)
