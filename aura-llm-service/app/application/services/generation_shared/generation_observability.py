from prometheus_client import Counter, Histogram

from app.application.services.generation_shared.processors.processor_observability import (  # noqa: F401
    log_extra,
)

generation_total = Counter(
    "aura_generation_total",
    "Generation request outcomes by service.",
    labelnames=("label", "call_mode", "outcome"),
)
generation_seconds = Histogram(
    "aura_generation_seconds",
    "End-to-end generation duration by service.",
    labelnames=("label", "call_mode"),
)
