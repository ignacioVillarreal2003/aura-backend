"""Helpers shared by the structured-generation services to sanitise LLM output."""

_BULLET_PREFIX_CHARS = "•-*0123456789.) "


def clean_text(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def fallback_lines(raw: str) -> list[str]:
    """Split a non-JSON LLM answer into usable lines, stripping bullet markers."""
    return [
        stripped
        for line in raw.splitlines()
        if line.strip()
        if (stripped := line.strip().lstrip(_BULLET_PREFIX_CHARS))
    ]
