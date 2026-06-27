import functools
import inspect
import json
import logging
from contextlib import contextmanager, nullcontext
from typing import Any, Iterator, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_TRACER_NAME = "aura-llm-service"
_SPAN_KIND_ATTR = "openinference.span.kind"
_INPUT_VALUE_ATTR = "input.value"
_OUTPUT_VALUE_ATTR = "output.value"

_active = False


class TracingSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRACING_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(default=False)
    endpoint: str = Field(default="http://localhost:6006/v1/traces")
    project_name: str = Field(default="aura-llm-service")


def setup_tracing(settings: Optional[TracingSettings] = None) -> bool:
    global _active
    settings = settings or TracingSettings()
    if not settings.enabled:
        return False

    try:
        from openinference.instrumentation.langchain import LangChainInstrumentor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry import trace
    except ImportError:
        logger.warning(
            "TRACING_ENABLED is set but tracing dependencies are not installed. "
            "Run: pip install -r requirements/requirements.txt"
        )
        return False

    try:
        resource = Resource.create({"openinference.project.name": settings.project_name})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.endpoint)))
        trace.set_tracer_provider(provider)
        LangChainInstrumentor().instrument(tracer_provider=provider)
        _active = True
        logger.info(
            "LLM tracing enabled — sending OpenInference spans to Phoenix.",
            extra={"endpoint": settings.endpoint, "project": settings.project_name},
        )
        return True
    except Exception:
        logger.exception("Failed to initialize LLM tracing; continuing without it.")
        return False


def is_tracing_active() -> bool:
    return _active


@contextmanager
def generation_span(name: str, input_value: Optional[str] = None) -> Iterator[Any]:
    if not _active:
        with nullcontext():
            yield None
        return
    from opentelemetry import trace

    tracer = trace.get_tracer(_TRACER_NAME)
    with tracer.start_as_current_span(name) as span:
        span.set_attribute(_SPAN_KIND_ATTR, "CHAIN")
        if input_value:
            span.set_attribute(_INPUT_VALUE_ATTR, input_value)
        yield span


def trace_generation(name: Optional[str] = None):
    def _resolve_name(self: Any) -> str:
        return name or getattr(self, "label", None) or type(self).__name__

    def _request_input(args: tuple) -> Optional[str]:
        if not args:
            return None
        messages = getattr(args[0], "messages", None)
        if messages:
            content = getattr(messages[-1], "content", None)
            if isinstance(content, str):
                return content
        return None

    def decorator(method):
        if inspect.isasyncgenfunction(method):
            @functools.wraps(method)
            async def gen_wrapper(self, *args, **kwargs):
                # Streaming: el async generator lo consume Starlette en otra Task,
                # así que NO usamos start_as_current_span (el attach/detach de
                # contextvars cruzaría de contexto y rompería con
                # "Token was created in a different Context"). Creamos el span
                # suelto y lo cerramos en finally.
                if not _active:
                    async for item in method(self, *args, **kwargs):
                        yield item
                    return

                from opentelemetry import trace

                tracer = trace.get_tracer(_TRACER_NAME)
                span = tracer.start_span(_resolve_name(self))
                span.set_attribute(_SPAN_KIND_ATTR, "CHAIN")
                input_value = _request_input(args)
                if input_value:
                    span.set_attribute(_INPUT_VALUE_ATTR, input_value)
                try:
                    async for item in method(self, *args, **kwargs):
                        yield item
                finally:
                    span.end()

            return gen_wrapper

        @functools.wraps(method)
        async def wrapper(self, *args, **kwargs):
            with generation_span(_resolve_name(self), _request_input(args)):
                return await method(self, *args, **kwargs)

        return wrapper

    return decorator


@contextmanager
def retrieval_span(name: str, queries: list[str]) -> Iterator[Any]:
    if not _active:
        with nullcontext():
            yield None
        return
    from opentelemetry import trace

    tracer = trace.get_tracer(_TRACER_NAME)
    with tracer.start_as_current_span(name) as span:
        span.set_attribute(_SPAN_KIND_ATTR, "RETRIEVER")
        span.set_attribute(_INPUT_VALUE_ATTR, "\n".join(queries))
        yield span


def record_retrieved_documents(span: Any, fragments: list) -> None:
    if span is None:
        return
    for index, fragment in enumerate(fragments):
        prefix = f"retrieval.documents.{index}.document"
        span.set_attribute(f"{prefix}.id", str(fragment.id))
        span.set_attribute(f"{prefix}.content", fragment.content)
        span.set_attribute(
            f"{prefix}.metadata",
            json.dumps(
                {
                    "document_id": fragment.document_id,
                    "document_name": fragment.document.name,
                    "fragment_index": fragment.fragment_index,
                },
                ensure_ascii=False,
            ),
        )


def set_span_output(span: Any, value: str) -> None:
    if span is None or not value:
        return
    span.set_attribute(_OUTPUT_VALUE_ATTR, value)
