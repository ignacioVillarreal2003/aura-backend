from enum import Enum


class ReaderType(str, Enum):
    docling = "docling"
    digital_pdf = "digital_pdf"
    digital_docx = "digital_docx"
    scanned_pdf = "scanned_pdf"
    scanned_docx = "scanned_docx"
    plain_text = "plain_text"
    csv = "csv"
