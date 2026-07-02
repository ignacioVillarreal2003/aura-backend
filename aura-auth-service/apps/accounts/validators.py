"""Validadores reutilizables del dominio de cuentas."""

import re

from django.core.exceptions import ValidationError

# Letras Unicode (incluye acentos: á, ñ, ü...) y separadores propios de los
# nombres de persona (espacio, guion y apóstrofo). Excluye dígitos y cualquier
# otro símbolo. Ejemplos válidos: "José Pérez", "Jean-Luc", "O'Brien".
_HUMAN_NAME_RE = re.compile(r"^[^\W\d_]+(?:[ '\-][^\W\d_]+)*$", re.UNICODE)


def validate_human_name(value):
    """Acepta solo letras y espacios (sin números ni símbolos).

    No exige valor: los campos opcionales (vacíos/None) pasan sin error; la
    obligatoriedad se controla aparte.
    """
    if value is None:
        return
    cleaned = value.strip()
    if not cleaned:
        return
    if not _HUMAN_NAME_RE.match(cleaned):
        raise ValidationError(
            'El nombre solo puede contener letras y espacios, sin números ni símbolos.'
        )
