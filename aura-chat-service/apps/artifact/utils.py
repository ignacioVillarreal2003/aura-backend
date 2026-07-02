import re
from typing import Any


def safe_filename(title: str) -> str:
    return re.sub(r"[^\w\-]", "_", title[:60])


def _fragment_document_key(fragment: Any) -> Any:
    if not isinstance(fragment, dict):
        return None
    document = fragment.get("document")
    if isinstance(document, dict) and document.get("id") is not None:
        return document.get("id")
    return fragment.get("document_id")


def deduplicate_fragments_by_document(fragments: Any) -> Any:
    if not isinstance(fragments, list):
        return fragments

    by_document: dict[Any, dict[str, Any]] = {}
    order: list[Any] = []
    extras: list[Any] = []

    for fragment in fragments:
        key = _fragment_document_key(fragment)
        if key is None:
            extras.append(fragment)
            continue
        existing = by_document.get(key)
        if existing is None:
            entry = dict(fragment)
            entry["matched_fragments"] = 1
            by_document[key] = entry
            order.append(key)
        else:
            existing["matched_fragments"] = existing.get("matched_fragments", 1) + 1

    deduped = [by_document[key] for key in order]
    deduped.extend(extras)
    return deduped
