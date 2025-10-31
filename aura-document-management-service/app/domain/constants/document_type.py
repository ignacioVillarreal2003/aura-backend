from enum import Enum


class DocumentType(str, Enum):
    pdf = "pdf"
    docx = "docx"