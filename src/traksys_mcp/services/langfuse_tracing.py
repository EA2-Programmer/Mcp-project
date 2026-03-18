"""
Langfuse tracing service for TrakSYS MCP tools.

Wraps Langfuse v3 trace/span lifecycle with clean async context managers.
When tracing is disabled or Langfuse is unavailable, all operations are
silent no-ops — callers never need to branch on tracing state.
"""

import logging
import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Generator, AsyncGenerator, Optional

from src.traksys_mcp.config.setting import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Null object — used when tracing is disabled
# ---------------------------------------------------------------------------

class _NoOpSpan:
    """Silent no-op span. All operations succeed without side effects."""

    def update(self, **kwargs) -> None:
        pass

    def end(self) -> None:
        pass

    def span(self, **kwargs) -> "_NoOpSpan":
        return self

    def generation(self, **kwargs) -> "_NoOpSpan":
        return self

    def event(self, **kwargs) -> "_NoOpSpan":
        return self


_NOOP = _NoOpSpan()


class SpanWrapper:
    """
    Wraps a Langfuse span and its parent trace.

    Responsibilities:
    - Forwards update/generation/span/event calls to the underlying span
    - Tracks child spans so they are ended before the parent
    - Ends the trace when end() is called
    """

    __slots__ = ("_span", "_trace", "_children")

    def __init__(self, span: Any, trace: Any) -> None:
        self._span = span
        self._trace = trace
        self._children: list[Any] = []

    def update(self, **kwargs) -> None:
        self._span.update(**kwargs)

    def span(self, name: str, input: Any = None, **kwargs) -> Any:
        child = self._span.span(name=name, input=input, **kwargs)
        self._children.append(child)
        return child

    def generation(self, name: str, input: Any = None, output: Any = None, **kwargs) -> Any:
        child = self._span.generation(name=name, input=input, output=output, **kwargs)
        self._children.append(child)
        return child

    def event(self, name: str, input: Any = None, **kwargs) -> Any:
        child = self._span.event(name=name, input=input, **kwargs)
        self._children.append(child)
        return child

    def end(self) -> None:
        for child in self._children:
            child.end()
        self._span.end()
        self._trace.end()


class TracingService:
    """
    Langfuse tracing service for MCP tools.

    Usage:
        async with tracing.trace_tool("get_batches", inputs) as span:
            result = await do_work()
            tracing.set_output(span, result)
    """

    def __init__(self) -> None:
        self._client: Any = None
        self._enabled = False
        self._init()

    def _init(self) -> None:
        if not settings.ENABLE_TRACING:
            logger.info("Tracing disabled (ENABLE_TRACING=False)")
            return

        if not settings.LANGFUSE_SECRET_KEY or not settings.LANGFUSE_PUBLIC_KEY:
            logger.warning("Tracing disabled: LANGFUSE_SECRET_KEY or LANGFUSE_PUBLIC_KEY not set")
            return

        try:
            from langfuse import Langfuse

            self._client = Langfuse(
                secret_key=settings.LANGFUSE_SECRET_KEY.get_secret_value(),
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                host=settings.LANGFUSE_BASE_URL,
                debug=settings.LOG_LEVEL == "DEBUG",
                flush_at=20,
                flush_interval=10,
            )
            self._client.auth_check()
            self._enabled = True
            logger.info("Langfuse tracing enabled → %s", settings.LANGFUSE_BASE_URL)

        except ImportError:
            logger.warning("Tracing disabled: langfuse package not installed")
        except Exception as e:
            logger.error("Langfuse init failed: %s", e)

    @property
    def enabled(self) -> bool:
        return self._enabled


    @asynccontextmanager
    async def trace_tool(
        self, tool_name: str, inputs: dict
    ) -> AsyncGenerator[Any, None]:
        """
        Root trace + span for a single tool execution.

        Yields a SpanWrapper on success, or _NOOP if tracing is off.
        """
        if not self._enabled:
            yield _NOOP
            return

        wrapper: Any = _NOOP
        try:
            trace = self._client.trace(
                name=f"tools/call_{tool_name}",
                input=inputs,
                metadata={
                    "server": "TrakSYS MCP",
                    "version": "1.0.0",
                    "transport": settings.SERVER_TRANSPORT,
                    "read_only": settings.READ_ONLY,
                },
                tags=["mcp", "traksys", f"tool:{tool_name}",
                      f"transport:{settings.SERVER_TRANSPORT}"],
            )
            span = trace.span(name=tool_name, input=inputs)
            wrapper = SpanWrapper(span, trace)
            yield wrapper

        except Exception as e:
            logger.error("Trace setup failed for %s: %s", tool_name, e)
            yield _NOOP
            return

        try:
            wrapper.end()
        except Exception as e:
            logger.debug("Span end error for %s: %s", tool_name, e)


    @contextmanager
    def db_span(
        self,
        parent: Any,
        name: str,
        sql_hash: str,
        params_count: int,
    ) -> Generator[Any, None, None]:
        """
        Child span for a single database query.
        """
        if not self._enabled or isinstance(parent, _NoOpSpan):
            yield _NOOP
            return

        child = parent.span(
            name=name,
            input={"sql_hash": sql_hash, "params_count": params_count},
        )
        try:
            yield child
        finally:
            try:
                child.end()
            except Exception as e:
                logger.debug("DB span end error: %s", e)


    def set_output(self, span: Any, output: dict) -> None:
        """
        Attach complete tool output to the span.

        Full raw data is preserved for complete observability.
        Langfuse handles large payloads efficiently; truncation is not needed.

        Args:
            span: The span to update
            output: Complete output data to attach
        """
        if not self._enabled or isinstance(span, _NoOpSpan):
            return

        # Send full, untruncated data
        span.update(output=output)
        if hasattr(span, "_trace"):
            span._trace.update(output=output)

    def record_error(self, span: Any, error: Exception, tool_name: str) -> None:
        """Attach error details to the span."""
        if not self._enabled or isinstance(span, _NoOpSpan):
            return

        span.update(
            level="ERROR",
            status_message=str(error),
            output={
                "error": str(error),
                "type": type(error).__name__,
                "tool": tool_name,
            },
        )

    def record_db_rows(
        self, span: Any, rows: int, execution_time: float | None = None
    ) -> None:
        """Attach query result count (and optional timing) to a DB child span."""
        if not self._enabled or isinstance(span, _NoOpSpan):
            return

        metadata: dict[str, Any] = {"rows": rows}
        if execution_time is not None:
            metadata["execution_ms"] = round(execution_time, 2)
        span.update(metadata=metadata)


    def shutdown(self) -> None:
        """Flush all pending spans before process exit."""
        if not self._enabled or not self._client:
            return
        try:
            self._client.flush()
            time.sleep(1)
            logger.info("Langfuse flushed on shutdown")
        except Exception as e:
            logger.error("Langfuse shutdown error: %s", e)


_instance: Optional[TracingService] = None


def register_instance(service: TracingService) -> None:
    global _instance
    _instance = service


def get_tracing_service() -> Optional[TracingService]:
    return _instance