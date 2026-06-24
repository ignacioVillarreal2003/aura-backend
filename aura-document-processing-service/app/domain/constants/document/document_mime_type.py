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

    @property
    def media_type(self) -> str:
        return _MEDIA_TYPES[self]

    @property
    def extension(self) -> str:
        return _EXTENSIONS[self]


_MEDIA_TYPES: dict[DocumentMimeType, str] = {
    DocumentMimeType.pdf: "application/pdf",
    DocumentMimeType.docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    DocumentMimeType.pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    DocumentMimeType.xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    DocumentMimeType.txt: "text/plain",
    DocumentMimeType.md: "text/markdown",
    DocumentMimeType.csv: "text/csv",
    DocumentMimeType.png: "image/png",
    DocumentMimeType.jpeg: "image/jpeg",
    DocumentMimeType.tiff: "image/tiff",
    DocumentMimeType.bmp: "image/bmp",
    DocumentMimeType.webp: "image/webp",
}

_EXTENSIONS: dict[DocumentMimeType, str] = {
    DocumentMimeType.pdf: ".pdf",
    DocumentMimeType.docx: ".docx",
    DocumentMimeType.pptx: ".pptx",
    DocumentMimeType.xlsx: ".xlsx",
    DocumentMimeType.txt: ".txt",
    DocumentMimeType.md: ".md",
    DocumentMimeType.csv: ".csv",
    DocumentMimeType.png: ".png",
    DocumentMimeType.jpeg: ".jpeg",
    DocumentMimeType.tiff: ".tiff",
    DocumentMimeType.bmp: ".bmp",
    DocumentMimeType.webp: ".webp",
}
