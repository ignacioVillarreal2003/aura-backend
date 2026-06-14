from collections import defaultdict
from typing import Dict, List

from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


def build_document_context(fragments: List[FragmentResponse], max_context_chars: int) -> str:
    """Render fragments grouped per document, in fragment order, within a char budget.

    Section headers carry both the document id and its name so the synthesizer
    can produce verifiable [Documento #ID] citations.
    """
    if not fragments:
        return ""

    grouped: Dict[int, List[FragmentResponse]] = defaultdict(list)
    for fragment in fragments:
        grouped[fragment.document_id].append(fragment)

    for doc_id in grouped:
        grouped[doc_id].sort(key=lambda f: f.fragment_index)

    parts: List[str] = []
    total_chars = 0

    for doc_id, doc_fragments in grouped.items():
        doc_name = doc_fragments[0].document.name if doc_fragments[0].document else ""
        header = f"=== Documento #{doc_id}" + (f" — {doc_name}" if doc_name else "") + " ==="
        section_parts = [header]
        section_chars = len(header)

        for i, fragment in enumerate(doc_fragments, start=1):
            remaining = max_context_chars - total_chars - section_chars
            if remaining <= 0:
                break
            content = fragment.content[:remaining]
            fragment_text = f"\n[Fragmento {i}]\n{content}"
            section_parts.append(fragment_text)
            section_chars += len(fragment_text)

        section = "\n".join(section_parts)
        total_chars += len(section)
        parts.append(section)

        if total_chars >= max_context_chars:
            break

    return "\n\n".join(parts)
