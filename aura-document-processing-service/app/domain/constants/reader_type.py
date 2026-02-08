from enum import Enum


class ReaderType(str, Enum):
    digital_pdf = "digital_pdf"
    scanned_pdf = "scanned_pdf"
    digital_docx = "digital_docx"
    scanned_docx = "scanned_docx"
