"""Custom Prometheus metrics for the document-processing service.

Counters defined here register on the default Prometheus registry, the same one
the FastAPI instrumentator exposes at ``/metrics`` (see ``app/main.py``). Define
each metric once at module load; Prometheus rejects duplicate registration.
"""

from prometheus_client import Counter

# Incremented whenever ingestion was configured for the structure-aware Docling
# chunker but a document had to fall back to the flat-text splitters, losing its
# structural metadata (section_path, page, bbox). The ``reason`` label separates
# operational causes:
#   - "exception":   structural chunking raised while processing the document.
#   - "unavailable": Docling/its dependencies are not installed at runtime.
# Normal routing (unsupported format, classic splitter configured) is NOT counted.
structural_chunk_fallback_total = Counter(
    "aura_document_structural_chunk_fallback_total",
    "Documents that fell back from structural to flat-text chunking.",
    ["reason"],
)
