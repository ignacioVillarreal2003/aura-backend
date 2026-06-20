from prometheus_client import Counter

structural_chunk_fallback_total = Counter(
    "aura_document_structural_chunk_fallback_total",
    "Documents that fell back from structural to flat-text chunking.",
    ["reason"],
)
