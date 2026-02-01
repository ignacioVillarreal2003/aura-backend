from enum import Enum


class ReaderType(str, Enum):
    DIGITAL_PDF = "digital_pdf"
    SCANNED_PDF = "scanned_pdf",
    DOCX = "docx"
