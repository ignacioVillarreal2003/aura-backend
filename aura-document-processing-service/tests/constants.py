"""Test payloads; MIME strings must match CreateDocumentServiceSettings defaults."""

# Typo preserved to match app settings (document_controllers suffix).
CT_PDF = "application/pdf"
CT_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document_controllers"

PDF_MINIMAL = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
DOCX_ZIP_PREFIX = b"PK\x03\x04" + b"\x00" * 40
