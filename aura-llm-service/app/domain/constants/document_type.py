from enum import Enum


class DocumentType(str, Enum):
    manual = "manual"
    informe = "informe"
    orden = "orden"
    doctrina = "doctrina"
    otro = "otro"
