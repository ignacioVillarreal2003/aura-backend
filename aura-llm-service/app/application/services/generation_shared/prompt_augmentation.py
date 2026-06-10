def augment_system_prompt(
    base: str,
    system_prompt: str | None,
    response_style: str | None,
) -> str:
    extra = ""
    if system_prompt and system_prompt.strip():
        extra += f"\n\n## CONTEXTO DEL OPERADOR\n{system_prompt.strip()}"
    if response_style and response_style.strip():
        extra += f"\n\n## ESTILO DE RESPUESTA\n{response_style.strip()}"
    return base + extra if extra else base
