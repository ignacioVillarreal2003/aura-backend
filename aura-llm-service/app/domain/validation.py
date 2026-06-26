import re
from typing import Annotated, Optional
from pydantic import AfterValidator

_CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def sanitize_control_chars(value: str) -> str:
    return _CONTROL_CHARS_PATTERN.sub("", value)


def stripped_non_blank(value: str, message: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(message)
    return stripped


def normalize_optional_prompt(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = sanitize_control_chars(value).strip()
    return cleaned or None


OptionalPrompt = Annotated[Optional[str], AfterValidator(normalize_optional_prompt)]
