from prometheus_client import Counter, Histogram

processing_total = Counter(
    "aura_processing_total",
    "Structured processing request outcomes by service.",
    labelnames=("label", "outcome"),
)
processing_seconds = Histogram(
    "aura_processing_seconds",
    "End-to-end structured processing duration by service.",
    labelnames=("label",),
)
