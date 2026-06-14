_BULLET_PREFIX_CHARS = "•-*0123456789.) "


def clean_text(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def fallback_lines(raw: str) -> list[str]:
    return [
        stripped
        for line in raw.splitlines()
        if line.strip()
        if (stripped := line.strip().lstrip(_BULLET_PREFIX_CHARS))
    ]
