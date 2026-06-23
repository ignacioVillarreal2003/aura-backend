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


def split_markdown_doc(raw: str) -> tuple[str, str, str]:
    """Split a Markdown document into (title, description, body).

    Used as a fallback when an LLM was asked for JSON {title, description, body}
    but returned plain Markdown instead: the first heading (or first line) is the
    title, the first paragraph after it is the description (lead), and the body is
    everything after the title line (so the title is not repeated inside it).
    """
    text = (raw or "").strip()
    if not text:
        return "", "", ""

    lines = text.split("\n")
    title = ""
    body_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        title = stripped.lstrip("#").strip() if stripped.startswith("#") else stripped
        body_start = i + 1
        break

    description = ""
    for line in lines[body_start:]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            break
        description = stripped
        break

    body = "\n".join(lines[body_start:]).strip()
    return title, description, body
