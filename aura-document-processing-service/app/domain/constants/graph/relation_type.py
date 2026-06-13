import re
from typing import Final

_VALID_RELATION_TYPE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[a-z][a-z0-9_]{0,62}[a-z0-9]$"
)

DEFAULT_ALLOWED_RELATION_TYPES: Final[tuple[str, ...]] = (
    "related_to",
    "part_of",
    "located_in",
    "works_for",
    "founded",
    "founded_by",
    "produces",
    "uses",
    "owns",
    "owned_by",
    "occurred_at",
    "occurred_on",
    "participated_in",
    "subsidiary_of",
    "parent_of",
    "spouse_of",
    "child_of",
    "depends_on",
    "competes_with",
    "collaborates_with",
    "mentioned_in",
)


def normalize_relation_type(raw: str) -> str:
    if not raw:
        return "related_to"
    candidate = raw.strip().lower()
    candidate = re.sub(r"[\s\-/]+", "_", candidate)
    candidate = re.sub(r"[^a-z0-9_]", "", candidate)
    candidate = re.sub(r"_+", "_", candidate).strip("_")
    if not candidate or len(candidate) > 64:
        return "related_to"
    if not _VALID_RELATION_TYPE_PATTERN.match(candidate):
        return "related_to"
    return candidate
