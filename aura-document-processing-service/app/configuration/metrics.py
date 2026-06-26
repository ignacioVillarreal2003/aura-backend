import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)

_PIPELINE_BUCKETS = (0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600)
_LLM_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
_CONSUMER_BUCKETS = (0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300)
_FRAGMENT_BUCKETS = (1, 5, 10, 25, 50, 100, 250, 500, 1000, 5000)

document_ingestion_total = Counter(
    "aura_document_ingestion_total",
    "Documents processed by the ingestion pipeline, by terminal result.",
    ["result"],
)

document_ingestion_duration_seconds = Histogram(
    "aura_document_ingestion_duration_seconds",
    "End-to-end wall-clock duration of the document ingestion pipeline.",
    buckets=_PIPELINE_BUCKETS,
)

pipeline_stage_duration_seconds = Histogram(
    "aura_document_pipeline_stage_duration_seconds",
    "Duration of an individual ingestion pipeline stage.",
    ["stage"],
    buckets=_PIPELINE_BUCKETS,
)

pipeline_stage_failures_total = Counter(
    "aura_document_pipeline_stage_failures_total",
    "Ingestion pipeline failures attributed to the stage that raised them.",
    ["stage"],
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

llm_request_duration_seconds = Histogram(
    "aura_llm_request_duration_seconds",
    "Latency of a call to the LLM service, by logical operation.",
    ["operation"],
    buckets=_LLM_BUCKETS,
)

llm_requests_total = Counter(
    "aura_llm_requests_total",
    "LLM service calls by operation and outcome.",
    ["operation", "result"],
)

messages_consumed_total = Counter(
    "aura_messages_consumed_total",
    "Queue messages handled by a consumer, by queue and disposition.",
    ["queue", "result"],
)


_RERANK_SCORE_BUCKETS = (0.0, 0.1, 0.2, 0.3, 0.35, 0.5, 0.7, 0.85, 0.95, 1.0)

retrieval_top_rerank_score = Histogram(
    "aura_retrieval_top_rerank_score",
    "Top cross-encoder score per question retrieval (relevance-confidence proxy).",
    buckets=_RERANK_SCORE_BUCKETS,
)

retrieval_lane_fragments_total = Counter(
    "aura_retrieval_lane_fragments_total",
    "Final retrieved fragments attributed to each lane that surfaced them "
    "(vector_raw, vector_contextual, bm25_raw, bm25_contextual).",
    ["lane"],
)

retrieval_rerank_fallback_total = Counter(
    "aura_retrieval_rerank_fallback_total",
    "Reranks where the whole candidate pool scored below min_score "
    "(poor-match queries), by the action taken.",
    ["action"],
)

message_processing_duration_seconds = Histogram(
    "aura_message_processing_duration_seconds",
    "Time spent in the message handler (_process) per queue.",
    ["queue"],
    buckets=_CONSUMER_BUCKETS,
)


def llm_result_from_status(status_code: int | None) -> str:
    if status_code == 504:
        return "timeout"
    if status_code == 503:
        return "unavailable"
    return "http_error"


@contextmanager
def observe_stage(stage: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        pipeline_stage_duration_seconds.labels(stage=stage).observe(time.perf_counter() - start)


def patch_instrumentator_routing() -> None:
    from prometheus_fastapi_instrumentator import routing
    from starlette.routing import Match

    def _safe_get_route_name(scope, routes, route_name=None):
        for route in routes:
            match, child_scope = route.matches(scope)
            if match == Match.FULL:
                route_name = getattr(route, "path", "") or ""
                child_scope = {**scope, **child_scope}
                sub_routes = getattr(route, "routes", None) or getattr(
                    getattr(route, "router", None), "routes", None
                )
                if sub_routes:
                    child_route_name = _safe_get_route_name(child_scope, sub_routes, route_name)
                    route_name = None if child_route_name is None else route_name + child_route_name
                return route_name or None
            if match == Match.PARTIAL and route_name is None:
                route_name = getattr(route, "path", None)
        return None

    routing._get_route_name = _safe_get_route_name
    logger.info("Patched prometheus-fastapi-instrumentator routing for _IncludedRouter compatibility.")
