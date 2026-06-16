import logging
import time
from contextlib import contextmanager
from typing import Iterator
from prometheus_client import Counter, Histogram

from app.infrastructure.http.request_id_context import get_request_id

logger = logging.getLogger(__name__)

processor_stage_seconds = Histogram(
    "aura_processor_stage_seconds",
    "Wall-clock duration of generation_shared processor stages.",
    labelnames=("stage",),
)

reformulation_total = Counter(
    "aura_query_reformulation_total",
    "Query reformulation outcomes.",
    labelnames=("outcome",),
)
reformulation_truncated_total = Counter(
    "aura_query_reformulation_truncated_total",
    "Reformulation outputs clipped by the token budget.",
    labelnames=("field",),
)

retrieval_total = Counter(
    "aura_context_retrieval_total",
    "Context retrieval outcomes.",
    labelnames=("outcome",),
)
retrieval_fragments_returned = Histogram(
    "aura_context_retrieval_fragments_returned",
    "Fragments kept after a context retrieval.",
    buckets=(0, 1, 2, 4, 8, 12, 20, 50, 100),
)
retrieval_failures_total = Counter(
    "aura_context_retrieval_failures_total",
    "Context retrieval failures by reason.",
    labelnames=("reason",),
)

reduction_passes = Histogram(
    "aura_context_reduction_passes",
    "Reduction passes performed per request.",
    buckets=(1, 2, 3, 4, 5),
)
reduction_compression_ratio = Histogram(
    "aura_context_reduction_compression_ratio",
    "Reduction output/input character ratio.",
    buckets=(0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5),
)
reduction_batch_failures_total = Counter(
    "aura_context_reduction_batch_failures_total",
    "Reduction batches that failed and were skipped (silent content loss).",
)
reduction_outcome_total = Counter(
    "aura_context_reduction_outcome_total",
    "Terminal outcome of the reduction loop.",
    labelnames=("outcome",),
)

attached_fetch_total = Counter(
    "aura_attached_documents_fetch_total",
    "Attached document fetch outcomes.",
    labelnames=("outcome",),
)
attached_documents_dropped_total = Counter(
    "aura_attached_documents_dropped_total",
    "Attached documents that contributed zero fragments after budgeting.",
)
attached_fragments_selected = Histogram(
    "aura_attached_documents_fragments_selected",
    "Attached fragments selected after budgeting.",
    buckets=(0, 1, 2, 5, 10, 20, 40, 60, 100),
)


@contextmanager
def timed(stage: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        try:
            processor_stage_seconds.labels(stage=stage).observe(time.perf_counter() - start)
        except Exception:
            logger.debug("Failed to record stage duration.", exc_info=True)


def log_extra(**fields: object) -> dict:
    request_id = get_request_id()
    if request_id:
        fields.setdefault("request_id", request_id)
    return fields
