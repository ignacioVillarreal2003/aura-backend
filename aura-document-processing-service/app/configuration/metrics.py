"""Custom Prometheus metrics for business-level observability.

These complement the generic HTTP instrumentation wired in ``app.main`` (via
prometheus-fastapi-instrumentator). Every metric here registers on the default
prometheus_client registry, so it is exposed automatically on ``/metrics``.

Naming convention: ``aura_<domain>_<name>_<unit>``. Counters end in ``_total``,
histograms end in the unit (``_seconds``). Keep label cardinality bounded — only
low-cardinality dimensions (stage, operation, queue, result), never ids or names.
"""
import time
from collections.abc import Iterator
from contextlib import contextmanager

from prometheus_client import Counter, Histogram

# Buckets tuned for the async document pipeline: stages range from sub-second
# (split/clean) to minutes (read/embed of large files).
_PIPELINE_BUCKETS = (0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600)
# LLM calls are network-bound with timeouts in the tens of seconds.
_LLM_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
# Per-message consumer processing time across all queues.
_CONSUMER_BUCKETS = (0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300)
# Number of fragments produced per ingested document.
_FRAGMENT_BUCKETS = (1, 5, 10, 25, 50, 100, 250, 500, 1000, 5000)


# ── Document ingestion pipeline ─────────────────────────────────────────────────

document_ingestion_total = Counter(
    "aura_document_ingestion_total",
    "Documents processed by the ingestion pipeline, by terminal result.",
    ["result"],  # success | failure
)

document_ingestion_duration_seconds = Histogram(
    "aura_document_ingestion_duration_seconds",
    "End-to-end wall-clock duration of the document ingestion pipeline.",
    buckets=_PIPELINE_BUCKETS,
)

pipeline_stage_duration_seconds = Histogram(
    "aura_document_pipeline_stage_duration_seconds",
    "Duration of an individual ingestion pipeline stage.",
    ["stage"],  # chunk | embed | persist
    buckets=_PIPELINE_BUCKETS,
)

pipeline_stage_failures_total = Counter(
    "aura_document_pipeline_stage_failures_total",
    "Ingestion pipeline failures attributed to the stage that raised them.",
    ["stage"],  # read | clean | split | embed | persist | unexpected
)

document_fragments_per_document = Histogram(
    "aura_document_fragments_per_document",
    "Number of fragments produced per successfully ingested document.",
    buckets=_FRAGMENT_BUCKETS,
)

structural_chunk_fallback_total = Counter(
    "aura_document_structural_chunk_fallback_total",
    "Documents that fell back from structural to flat-text chunking.",
    ["reason"],
)


# ── LLM provider ────────────────────────────────────────────────────────────────

llm_request_duration_seconds = Histogram(
    "aura_llm_request_duration_seconds",
    "Latency of a call to the LLM service, by logical operation.",
    ["operation"],  # classify_document | enrich_fragment | extract_entities_relations | translate_graph_query
    buckets=_LLM_BUCKETS,
)

llm_requests_total = Counter(
    "aura_llm_requests_total",
    "LLM service calls by operation and outcome.",
    ["operation", "result"],  # result: success | timeout | unavailable | http_error | invalid_response | error
)


# ── Messaging / queue throughput ────────────────────────────────────────────────

messages_consumed_total = Counter(
    "aura_messages_consumed_total",
    "Queue messages handled by a consumer, by queue and disposition.",
    ["queue", "result"],  # ack | nack | dropped
)

message_processing_duration_seconds = Histogram(
    "aura_message_processing_duration_seconds",
    "Time spent in the message handler (_process) per queue.",
    ["queue"],
    buckets=_CONSUMER_BUCKETS,
)


# ── Helpers ─────────────────────────────────────────────────────────────────────

def llm_result_from_status(status_code: int | None) -> str:
    """Map an LlmProviderException status code to a stable ``result`` label."""
    if status_code == 504:
        return "timeout"
    if status_code == 503:
        return "unavailable"
    return "http_error"


@contextmanager
def observe_stage(stage: str) -> Iterator[None]:
    """Record the wall-clock duration of a pipeline ``stage`` on success or failure.

    Works around an ``await`` because the bracketed coroutine suspends and resumes
    within the ``with`` block, so the timing spans the full awaited operation.
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        pipeline_stage_duration_seconds.labels(stage=stage).observe(time.perf_counter() - start)
