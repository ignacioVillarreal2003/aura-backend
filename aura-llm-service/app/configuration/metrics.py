import logging
from typing import Any, Optional
from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)

_UNKNOWN_MODEL = "unknown"

llm_tokens_total = Counter(
    "aura_llm_tokens_total",
    "Total tokens processed by the LLM, split by direction.",
    labelnames=("model", "direction"),
)

llm_invocation_seconds = Histogram(
    "aura_llm_invocation_seconds",
    "Latency of non-streaming LLM invocations in seconds.",
    labelnames=("model",),
)

guardrails_blocked_total = Counter(
    "aura_guardrails_blocked_total",
    "Requests/responses blocked by guardrails, by stage (input/output).",
    labelnames=("stage",),
)


def model_name_of(llm: Any) -> str:
    for candidate in (llm, getattr(llm, "bound", None)):
        model = getattr(candidate, "model", None)
        if isinstance(model, str) and model:
            return model
    return _UNKNOWN_MODEL


def record_llm_usage(
        model: Optional[str],
        input_tokens: Optional[int],
        output_tokens: Optional[int],
        duration_seconds: Optional[float],
) -> None:
    try:
        safe_model = model or _UNKNOWN_MODEL
        if duration_seconds is not None:
            llm_invocation_seconds.labels(model=safe_model).observe(duration_seconds)
        if input_tokens:
            llm_tokens_total.labels(model=safe_model, direction="input").inc(input_tokens)
        if output_tokens:
            llm_tokens_total.labels(model=safe_model, direction="output").inc(output_tokens)
    except Exception:
        # Metrics must never break a request.
        logger.debug("Failed to record LLM usage metrics.", exc_info=True)


def usage_tokens(message: Any) -> tuple[Optional[int], Optional[int]]:
    usage = getattr(message, "usage_metadata", None)
    if isinstance(usage, dict):
        return usage.get("input_tokens"), usage.get("output_tokens")
    return None, None


def record_guardrails_block(stage: str) -> None:
    try:
        guardrails_blocked_total.labels(stage=stage).inc()
    except Exception:
        logger.debug("Failed to record guardrails block metric.", exc_info=True)
