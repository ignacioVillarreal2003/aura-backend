import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


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
        start = s.find("{")
        end = s.rfind("}")
        if start < 0 or end <= start:
            logger.warning("Could not locate JSON object in LLM output")
            raise
        parsed = json.loads(s[start:end + 1])

    if not isinstance(parsed, dict):
        raise TypeError(f"Expected JSON object, got {type(parsed).__name__}")
    return parsed
