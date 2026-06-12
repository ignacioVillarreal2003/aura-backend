import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _extract_balanced_object(s: str) -> str:
    start = s.find("{")
    if start < 0:
        return ""
    depth = 0
    in_string = False
    escape_next = False
    for i, ch in enumerate(s[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
    return ""


def parse_json_object(text: str) -> dict[str, Any]:
    s = text.strip()

    if s.startswith("```"):
        lines = s.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()

    try:
        parsed = json.loads(s)
    except json.JSONDecodeError:
        candidate = _extract_balanced_object(s)
        if not candidate:
            logger.warning("Could not locate JSON object in LLM output")
            raise
        parsed = json.loads(candidate)

    if not isinstance(parsed, dict):
        raise TypeError(f"Expected JSON object, got {type(parsed).__name__}")
    return parsed
