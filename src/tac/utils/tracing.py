"""Optional OpenTelemetry tracing.

TAC emits spans through the OpenTelemetry API when ``opentelemetry-api`` is
installed (`pip install twilio-agent-connect[tracing]`). Nothing is recorded
until the application configures a tracer provider, and without the package
every helper here is a no-op.

Spans carry call data (phone numbers, transcripts, tool arguments), so export
them only to a backend you trust with it.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, Protocol

try:
    from opentelemetry import context as otel_context, trace

    _ENABLED = True
except ImportError:  # pragma: no cover - exercised only without the extra
    _ENABLED = False

_TRACER_NAME = "tac"


class SpanLike(Protocol):
    def set_attribute(self, key: str, value: Any) -> None: ...


class _NoOpSpan:
    def set_attribute(self, key: str, value: Any) -> None:
        pass


def _clean(attributes: dict[str, Any] | None) -> dict[str, Any]:
    # OpenTelemetry rejects None attribute values.
    return {k: v for k, v in (attributes or {}).items() if v is not None}


@contextmanager
def start_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[SpanLike]:
    """Run the ``with`` block inside a span, current for the block's duration."""
    if not _ENABLED:
        yield _NoOpSpan()
        return
    tracer = trace.get_tracer(_TRACER_NAME)
    with tracer.start_as_current_span(name, attributes=_clean(attributes)) as span:
        yield span


def begin_span(name: str, attributes: dict[str, Any] | None = None) -> Callable[[], None]:
    """Start a span that stays current until the returned callable ends it.

    For a span whose lifetime doesn't fit one ``with`` block. Call the returned
    function from the same task; tasks created in between inherit the span.
    """
    if not _ENABLED:
        return lambda: None
    span = trace.get_tracer(_TRACER_NAME).start_span(name, attributes=_clean(attributes))
    token = otel_context.attach(trace.set_span_in_context(span))

    def end() -> None:
        otel_context.detach(token)
        span.end()

    return end
