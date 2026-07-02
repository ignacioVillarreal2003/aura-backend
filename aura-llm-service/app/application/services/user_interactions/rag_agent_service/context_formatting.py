from collections import defaultdict
from typing import Dict, List

from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


def _format_fragment_source(fragment: FragmentResponse) -> str:
    parts: List[str] = []
    if fragment.document and fragment.document.name:
        parts.append(fragment.document.name)
    section = fragment.heading or fragment.section_path
    if section:
        parts.append(section)
    if fragment.page_number is not None:
        parts.append(f"pág. {fragment.page_number}")
    return " · ".join(parts)


def build_document_context(fragments: List[FragmentResponse], max_context_chars: int) -> str:
    if not fragments:
        return ""

    grouped: Dict[int, List[FragmentResponse]] = defaultdict(list)
    for fragment in fragments:
        grouped[fragment.document_id].append(fragment)

    for doc_id in grouped:
        grouped[doc_id].sort(key=lambda f: f.fragment_index)

    parts: List[str] = []
    total_chars = 0

    for doc_fragments in grouped.values():
        for fragment in doc_fragments:
            remaining = max_context_chars - total_chars
            if remaining <= 0:
                break
            source = _format_fragment_source(fragment)
            label = f"[FUENTE — {source}]" if source else "[FUENTE]"
            content = fragment.content[:remaining]
            entry = f"{label}\n{content}"
            parts.append(entry)
            total_chars += len(entry)
        if total_chars >= max_context_chars:
            break

    return "\n\n".join(parts)
