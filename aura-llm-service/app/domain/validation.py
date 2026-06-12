def stripped_non_blank(value: str, message: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(message)
    return stripped
