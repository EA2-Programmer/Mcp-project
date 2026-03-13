import logging
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Optional, AsyncGenerator

from src.traksys_mcp.config.setting import settings

logger = logging.getLogger(__name__)


class _NoOpSpan:
    """Placeholder span used when tracing is disabled — all calls are silent no-ops."""
    def update(self, **kwargs) -> None: pass
    def end(self) -> None: pass
    def generation(self, **kwargs) -> None: pass
    def span(self, **kwargs) -> None: pass
    def event(self, **kwargs) -> None: pass


_NOOP = _NoOpSpan()


class SpanWrapper:
    """Wraps a Langfuse span to provide safe, exception-tolerant child span creation."""

    def __init__(self, span, trace):
        self._span = span
        self._trace = trace
        self._child_spans = []

    def update(self, **kwargs):
        if hasattr(self._span, "update"):
            try:
                self._span.update(**kwargs)
            except Exception as e:
                logger.debug("Span update error: %s", e)

    def generation(self, name: str, input: Any = None, output: Any = None, **kwargs):
        if hasattr(self._span, "generation"):
            try:
                gen = self._span.generation(name=name, input=input, output=output, **kwargs)
                self._child_spans.append(gen)
                return gen
            except Exception as e:
                logger.debug("Generation error: %s", e)
        return None

    def span(self, name: str, input: Any = None, **kwargs):
        if hasattr(self._span, "span"):
            try:
                child = self._span.span(name=name, input=input, **kwargs)
                self._child_spans.append(child)
                return child
            except Exception as e:
                logger.debug("Child span error: %s", e)
        return None

    def event(self, name: str, input: Any = None, **kwargs):
        if hasattr(self._span, "event"):
            try:
                evt = self._span.event(name=name, input=input, **kwargs)
                self._child_spans.append(evt)
                return evt
            except Exception as e:
                logger.debug("Event error: %s", e)
        return None

    def end(self):
        for child in self._child_spans:
            if hasattr(child, "end"):
                try:
                    child.end()
                except Exception:
                    pass
        if hasattr(self._span, "end"):
            try:
                self._span.end()
            except Exception as e:
                logger.debug("Span end error: %s", e)
        if hasattr(self._trace, "end"):
            try:
                self._trace.end()
            except Exception as e:
                logger.debug("Trace end error: %s", e)


class TracingService:
    """Langfuse v3.14.5 tracing service for MCP tools."""

    def __init__(self) -> None:
        self._enabled = False
        self._client = None

        if not settings.ENABLE_TRACING:
            logger.info("Tracing disabled (ENABLE_TRACING=False)")
            return

        secret = settings.LANGFUSE_SECRET_KEY
        public = settings.LANGFUSE_PUBLIC_KEY

        if not secret or not public:
            logger.warning("Tracing disabled: missing credentials")
            return

        try:
            from langfuse import Langfuse
            self._client = Langfuse(
                secret_key=secret.get_secret_value(),
                public_key=public,
                host=settings.LANGFUSE_BASE_URL,
                debug=settings.LOG_LEVEL == "DEBUG",
                flush_at=1,
                flush_interval=1,
            )
            self._client.auth_check()
            self._enabled = True
            logger.info("Langfuse v3 enabled: %s", settings.LANGFUSE_BASE_URL)
        except ImportError:
            logger.warning("langfuse not installed")
        except Exception as e:
            logger.error("Langfuse init failed: %s", e)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @asynccontextmanager
    async def trace_tool(self, tool_name: str, inputs: dict) -> AsyncGenerator[Any, None]:
        """Create a root trace + span for a tool execution."""
        if not self._enabled:
            yield _NOOP
            return

        trace = None
        try:
            from langfuse import get_client
            langfuse = get_client()

            trace = langfuse.trace(
                name=f"tools/call {tool_name}",
                input=inputs,
                metadata={
                    "server": "TrakSYS MCP",
                    "version": "1.0.0",
                    "transport": settings.SERVER_TRANSPORT,
                    "read_only": settings.READ_ONLY,
                },
                tags=["mcp", "traksys", "manufacturing", f"transport:{settings.SERVER_TRANSPORT}"],
            )
            span = trace.span(name=tool_name, input=inputs)
            wrapper = SpanWrapper(span, trace)
            logger.info("Created trace for %s", tool_name)
            yield wrapper
            langfuse.flush()

        except Exception as e:
            logger.error("Trace error in %s: %s", tool_name, e, exc_info=True)
            if trace:
                try:
                    trace.end()
                except Exception:
                    pass
            yield _NOOP

    @contextmanager
    def db_span(self, parent_span: Any, span_name: str, sql_hash: str, params_count: int):
        """Create a child span for a database query under the given parent span."""
        if not self._enabled or isinstance(parent_span, _NoOpSpan):
            yield _NOOP
            return

        child_span = None
        try:
            if hasattr(parent_span, "span"):
                child_span = parent_span.span(
                    name=span_name,
                    input={"sql_hash": sql_hash, "params_count": params_count},
                )
                yield child_span
                if child_span and hasattr(child_span, "end"):
                    child_span.end()
            else:
                yield _NOOP
        except Exception as e:
            logger.error("DB span error: %s", e)
            if child_span and hasattr(child_span, "end"):
                try:
                    child_span.end()
                except Exception:
                    pass
            yield _NOOP

    def set_output(self, span: Any, output: dict) -> None:
        """
        Set output on a span, capping any lists at 5 items to avoid large payloads
        in the Langfuse UI.
        """
        if not self._enabled or isinstance(span, _NoOpSpan):
            return

        try:
            output_copy = output.copy()
            for key, value in output_copy.items():
                if isinstance(value, list) and len(value) > 5:
                    output_copy[key] = {
                        "count": len(value),
                        "sample": value[:5],
                        "note": f"Showing first 5 of {len(value)} items",
                    }

            if hasattr(span, "update"):
                span.update(output=output_copy)
                logger.info("Output set with %d fields", len(output_copy))

            if hasattr(span, "_trace") and span._trace and hasattr(span._trace, "update"):
                span._trace.update(output=output_copy)

            from langfuse import get_client
            get_client().flush()

        except Exception as e:
            logger.error("Set output error: %s", e)

    def record_error(self, span: Any, error: Exception, tool_name: str) -> None:
        """Record an error on a span."""
        if not self._enabled or isinstance(span, _NoOpSpan):
            return

        try:
            if hasattr(span, "update"):
                span.update(
                    level="ERROR",
                    status_message=str(error),
                    output={"error": str(error), "type": type(error).__name__, "tool": tool_name},
                )
        except Exception as e:
            logger.debug("Record error failed: %s", e)

    def record_db_rows(self, span: Any, rows: int, execution_time: float = None) -> None:
        """Attach row count (and optional execution time) as span metadata."""
        if not self._enabled or isinstance(span, _NoOpSpan):
            return

        try:
            metadata = {"rows": rows}
            if execution_time is not None:
                metadata["execution_ms"] = round(execution_time, 2)
            if hasattr(span, "update"):
                span.update(metadata=metadata)
        except Exception as e:
            logger.debug("Record rows error: %s", e)

    def shutdown(self) -> None:
        """Flush pending spans and shut down the Langfuse client."""
        if self._enabled and self._client:
            try:
                self._client.flush()
                import time
                time.sleep(1)  # Give the background thread time to send before process exits
                logger.info("Langfuse flushed successfully")
            except Exception as e:
                logger.error("Shutdown error: %s", e)


_tracing_service_instance: Optional[TracingService] = None


def register_instance(service: TracingService) -> None:
    global _tracing_service_instance
    _tracing_service_instance = service


def get_tracing_service() -> Optional[TracingService]:
    return _tracing_service_instance