import re

_BULLET_PREFIX = re.compile(r"^\s*(?:[•\-*]+|\d+[.)])(?:\s+|$)")


def clean_text(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def fallback_lines(raw: str) -> list[str]:
    lines: list[str] = []
    for line in raw.splitlines():
        stripped = _BULLET_PREFIX.sub("", line.strip(), count=1).strip()
        if stripped:
            lines.append(stripped)
    return lines
