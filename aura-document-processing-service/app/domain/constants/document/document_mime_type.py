from enum import Enum


class DocumentMimeType(str, Enum):
    pdf = "pdf"
    docx = "docx"
    pptx = "pptx"
    xlsx = "xlsx"
    txt = "txt"
    md = "md"
    csv = "csv"
    png = "png"
    jpeg = "jpeg"
    tiff = "tiff"
    bmp = "bmp"
    webp = "webp"
