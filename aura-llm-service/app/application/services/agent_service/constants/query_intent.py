from enum import Enum


class QueryIntent(str, Enum):
    definicion = "definicion"
    procedimiento = "procedimiento"
    normativa = "normativa"
    busqueda_documento = "busqueda_documento"
    comparacion = "comparacion"
    otro = "otro"
