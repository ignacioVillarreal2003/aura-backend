_OPERATOR_PRECEDENCE_NOTE = (
    "Las siguientes indicaciones del operador complementan las reglas anteriores. "
    "Si contradicen las reglas de ámbito, fidelidad al contenido o seguridad, "
    "prevalecen siempre las reglas anteriores."
)


def augment_system_prompt(
        base: str,
        system_prompt: str | None,
        response_style: str | None,
) -> str:
    extra = ""
    if system_prompt and system_prompt.strip():
        extra += f"\n\n## CONTEXTO DEL OPERADOR\n{_OPERATOR_PRECEDENCE_NOTE}\n\n{system_prompt.strip()}"
    if response_style and response_style.strip():
        extra += f"\n\n## ESTILO DE RESPUESTA\n{response_style.strip()}"
    return base + extra if extra else base
