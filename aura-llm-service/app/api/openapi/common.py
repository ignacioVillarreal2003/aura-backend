from typing import Any, Optional, TypeVar, Union
from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorBodyHttp(BaseModel):
    error: str
    message: Union[str, dict[str, Any]]
    request_id: Optional[str] = None


class ValidationErrorItem(BaseModel):
    loc: list[Union[str, int]] = Field(...)
    msg: str
    type: str


class ErrorBodyValidation(BaseModel):
    error: str = "ValidationError"
    message: str = "La validación de la solicitud falló"
    detail: list[ValidationErrorItem]
    request_id: Optional[str] = None


class ErrorBodyApp(BaseModel):
    error: str
    message: str
    request_id: Optional[str] = None


def default_error_responses(
        *,
        include_400: bool = False,
        include_403: bool = True,
        include_404: bool = True,
        include_409: bool = False,
        include_413: bool = False,
        include_415: bool = False,
        include_422: bool = True,
        include_429: bool = True,
        include_502: bool = False,
        include_503: bool = False,
) -> dict[int, dict[str, Any]]:
    r: dict[int, dict[str, Any]] = {
        401: {
            "description": "Autenticación requerida o credenciales inválidas",
            "model": ErrorBodyHttp,
        },
    }
    if include_400:
        r[400] = {
            "description": "Solicitud inválida",
            "model": ErrorBodyApp,
        }
    if include_403:
        r[403] = {
            "description": "Acceso denegado por permisos o política",
            "model": ErrorBodyHttp,
        }
    if include_404:
        r[404] = {
            "description": "Recurso no encontrado",
            "model": ErrorBodyApp,
        }
    if include_409:
        r[409] = {
            "description": "Conflicto con el estado actual del recurso",
            "model": ErrorBodyApp,
        }
    if include_413:
        r[413] = {
            "description": "El archivo excede el tamaño máximo permitido",
            "model": ErrorBodyApp,
        }
    if include_415:
        r[415] = {
            "description": "Tipo de archivo no soportado",
            "model": ErrorBodyApp,
        }
    if include_422:
        r[422] = {
            "description": "La validación de la solicitud falló",
            "model": ErrorBodyValidation,
        }
    if include_429:
        r[429] = {
            "description": "Límite de solicitudes excedido; revisa la cabecera Retry-After",
            "model": ErrorBodyHttp,
        }
    if include_502:
        r[502] = {
            "description": "Error al comunicarse con una dependencia externa",
            "model": ErrorBodyApp,
        }
    if include_503:
        r[503] = {
            "description": "Servicio temporalmente no disponible",
            "model": ErrorBodyHttp,
        }
    r[500] = {
        "description": "Error interno del servidor",
        "model": ErrorBodyApp,
    }
    return r
