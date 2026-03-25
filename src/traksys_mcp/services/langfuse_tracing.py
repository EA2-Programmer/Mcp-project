"""
Langfuse tracing service for TrakSYS MCP tools.

Updated for Langfuse v3: Uses OpenTelemetry context managers instead of manual trace objects.
"""

import logging
import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Generator, AsyncGenerator, Optional

# NEW: Import propagate_attributes for v3 trace tagging
from langfuse import Langfuse, propagate_attributes

# Use relative import to avoid circular dependencies
from ..config.setting import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Null object — used when tracing is disabled
# ---------------------------------------------------------------------------

class _NoOpSpan:
    """Silent no-op span. All operations succeed without side effects."""

    def update(self, **kwargs) -> None: pass

    def end(self) -> None: pass

    def span(self, **kwargs) -> "_NoOpSpan": return self

    def generation(self, **kwargs) -> "_NoOpSpan": return self

    def event(self, **kwargs) -> "_NoOpSpan": return self


_NOOP = _NoOpSpan()


class OtelSpanWrapper:
    """
    Wraps an OpenTelemetry-based Langfuse observation context manager
    to provide the .update() and .end() methods expected by the orchestrator loop.
    """
    def __init__(self, context_manager: Any):
        self.context_manager = context_manager
        # Manual entry into the context manager to start the span
        self.span = self.context_manager.__enter__()

    def update(self, **kwargs):
        if hasattr(self.span, "update"):
            self.span.update(**kwargs)

    def end(self):
        # Manual exit from the context manager to end the span
        try:
            self.context_manager.__exit__(None, None, None)
        except Exception as e:
            logger.debug("Error ending Otel span: %s", e)

    def __getattr__(self, name):
        # Delegate other attributes to the underlying span object (e.g., .id)
        return getattr(self.span, name)


class SpanWrapper:
    """
    Wraps a Langfuse span and its root observation (trace).
    Ensures that updates (like output) are synced to both the span AND the trace
    so that data appears 'seamlessly' in the Langfuse dashboard.
    """

    def __init__(self, span: Any, root_span: Any, client: Optional[Langfuse] = None):
        # Rename attribute to avoid shadowing the .span() method!
        self._span = span
        self.root_span = root_span
        self.client = client

    def update(self, **kwargs):
        if hasattr(self._span, 'update'):
            self._span.update(**kwargs)
        if self.root_span and self.root_span != self._span and hasattr(self.root_span, 'update'):
            self.root_span.update(**kwargs)

    def end(self):
        # If it's an OtelSpanWrapper or stateful client, it might have .end()
        if hasattr(self._span, 'end'):
            self._span.end()

    def span(self, **kwargs) -> Any:
        """Creates a child span."""
        # Check if the underlying span has a .span method (not just the attribute)
        # In V3, LangfuseSpan often has a .span() method.
        if hasattr(self._span, 'span') and callable(self._span.span):
            return self._span.span(**kwargs)

        if self.client:
            # Fallback to high-level API with manual parent linking if method is missing
            parent_id = getattr(self._span, "id", None)
            ctx = self.client.start_as_current_observation(
                as_type="span",
                trace_context={"parent_observation_id": parent_id} if parent_id else None,
                **kwargs
            )
            return OtelSpanWrapper(ctx)

        return self._span

    def event(self, **kwargs) -> Any:
        """Creates a child event."""
        if hasattr(self._span, 'event') and callable(self._span.event):
            return self._span.event(**kwargs)

        if self.client:
            parent_id = getattr(self._span, "id", None)
            ctx = self.client.start_as_current_observation(
                as_type="event",
                trace_context={"parent_observation_id": parent_id} if parent_id else None,
                **kwargs
            )
            return OtelSpanWrapper(ctx)

        return self._span

    def generation(self, **kwargs) -> Any:
        """Creates a child generation."""
        if hasattr(self._span, 'generation') and callable(self._span.generation):
            return self._span.generation(**kwargs)

        if self.client:
            parent_id = getattr(self._span, "id", None)
            ctx = self.client.start_as_current_observation(
                as_type="generation",
                trace_context={"parent_observation_id": parent_id} if parent_id else None,
                **kwargs
            )
            return OtelSpanWrapper(ctx)

        return self._span

    def __getattr__(self, name):
        # Delegate other attributes (like .id) to the underlying span
        return getattr(self._span, name)


class TracingService:
    def __init__(self):
        self.enabled = settings.ENABLE_TRACING
        self._client: Optional[Langfuse] = None

        if self.enabled:
            try:
                secret_key = None
                if settings.LANGFUSE_SECRET_KEY:
                    secret_key = settings.LANGFUSE_SECRET_KEY.get_secret_value()

                self._client = Langfuse(
                    secret_key=secret_key,
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    host=settings.LANGFUSE_BASE_URL,  # V3 CHANGE: 'base_url' is now passed as 'host'
                )
                if not self._client.auth_check():
                    logger.error("Langfuse auth failed. Tracing disabled.")
                    self.enabled = False
                else:
                    logger.info("Langfuse tracing enabled and authenticated")
            except Exception as e:
                logger.error("Langfuse init error: %s", e)
                self.enabled = False

    @asynccontextmanager
    async def trace_chat(self, *args, **kwargs) -> AsyncGenerator[Any, None]:
        """Traces the main chat execution for the orchestrator."""
        if not self.enabled or not self._client:
            yield _NOOP
            return

        yielded = False
        try:
            # Create a top-level observation for the chat session
            with self._client.start_as_current_observation(
                    name="agent_chat_session",
                    as_type="span",
                    input={"args": args, "kwargs": kwargs}
            ) as root_span:
                yielded = True
                # We yield a wrapper around the root span.
                yield SpanWrapper(root_span, root_span, self._client)
        except Exception as e:
            if not yielded:
                logger.error("Chat trace setup failed: %s", e)
                yield _NOOP
            else:
                raise
        finally:
            if self._client:
                self._client.flush()

    @asynccontextmanager
    async def trace_tool(
            self, tool_name: str, inputs: dict
    ) -> AsyncGenerator[Any, None]:
        if not self.enabled or not self._client:
            yield _NOOP
            return

        yielded = False
        try:
            # V3 CHANGE 1: The first observation automatically becomes the "Trace"
            with self._client.start_as_current_observation(
                    as_type="span",
                    name=f"mcp_tool/{tool_name}",
                    input=inputs
            ) as root_span:

                # V3 CHANGE 2: Tags and trace metadata must be set via propagate_attributes
                with propagate_attributes(tags=["mcp", f"tool:{tool_name}"]):
                    # V3 CHANGE 3: The nested 'with' block automatically becomes a child Span
                    with self._client.start_as_current_observation(
                            as_type="span",
                            name=tool_name,
                            input=inputs
                    ) as child_span:
                        yielded = True
                        yield SpanWrapper(child_span, root_span, self._client)

        except Exception as e:
            if not yielded:
                logger.error("Trace setup failed: %s", e)
                yield _NOOP
            else:
                raise
        finally:
            if self._client:
                self._client.flush()

    def record_llm_call(self, parent: Any, turn: int, messages_count: int, tools_count: int) -> Any:
        """Records an LLM generation as a child of the trace."""
        if not self.enabled or not self._client or isinstance(parent, _NoOpSpan):
            return _NOOP

        parent_observation = parent.root_span if hasattr(parent, 'root_span') else parent
        parent_id = getattr(parent_observation, "id", None)

        try:
            # Use high-level API with trace_context for parent linking
            ctx = self._client.start_as_current_observation(
                name=f"llm-generation-turn-{turn}",
                as_type="generation",
                input={"messages_count": messages_count, "tools_count": tools_count},
                metadata={"turn": turn},
                trace_context={"parent_observation_id": parent_id} if parent_id else None
            )
            return OtelSpanWrapper(ctx)
        except Exception as e:
            logger.error("Failed to record LLM call: %s", e)
            return _NOOP

    def record_error(self, trace: Any, error: Exception, context: str = "") -> None:
        """Records an error event in the trace."""
        if not self.enabled or not self._client or isinstance(trace, _NoOpSpan):
            return

        target = trace.root_span if hasattr(trace, 'root_span') else trace
        parent_id = getattr(target, "id", None)

        try:
            # Use high-level API for consistency
            with self._client.start_as_current_observation(
                name="error",
                as_type="event",
                level="ERROR",
                status_message=str(error),
                input={"context": context, "error_type": type(error).__name__},
                trace_context={"parent_observation_id": parent_id} if parent_id else None
            ):
                pass

            # Also update the parent status
            if hasattr(target, "update"):
                target.update(level="ERROR", status_message=str(error))
        except Exception as e:
            logger.error("Failed to record error trace: %s", e)

    def set_trace_output(self, trace: Any, output: Any) -> None:
        """Updates the trace with final output data."""
        if not self.enabled or isinstance(trace, _NoOpSpan):
            return
        trace.update(output=output)

    def set_output(self, span: Any, output: Any) -> None:
        if not self.enabled or isinstance(span, _NoOpSpan):
            return
        span.update(output=output)

    @contextmanager
    def db_span(self, *args, **kwargs) -> Generator[Any, None, Any]:
        """Flexible span for database queries to prevent signature crashes."""
        if not self.enabled or not self._client:
            yield _NOOP
            return

        span_name = "database_query"
        if args:
            span_name = str(args[0])

        yielded = False
        try:
            with self._client.start_as_current_observation(
                    as_type="span",
                    name=span_name,
                    input={"args": [str(a) for a in args], "kwargs": str(kwargs)}
            ) as root_span:
                with self._client.start_as_current_observation(
                        as_type="span",
                        name="query_execution",
                ) as child_span:
                    yielded = True
                    yield child_span
        except Exception:
            if not yielded:
                yield _NOOP
            else:
                raise
        finally:
            if self._client:
                self._client.flush()

    def record_db_rows(self, span: Any, rows: int, execution_time: float | None = None) -> None:
        if not self.enabled or isinstance(span, _NoOpSpan):
            return

        metadata = {"rows": rows}
        if execution_time is not None:
            metadata["execution_ms"] = round(execution_time, 2)
        span.update(metadata=metadata)

    def shutdown(self) -> None:
        if self.enabled and self._client:
            self._client.flush()
            time.sleep(1)


_instance: Optional[TracingService] = None


def register_instance(service: TracingService) -> None:
    global _instance
    _instance = service


def get_tracing_service() -> Optional[TracingService]:
    return _instance


def init_tracing() -> TracingService:
    service = TracingService()
    register_instance(service)
    return service
