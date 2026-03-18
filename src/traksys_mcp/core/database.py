import asyncio
import hashlib
import logging
import re
from contextlib import contextmanager
from typing import Any, Optional

import pyodbc

from src.traksys_mcp.config.setting import settings
from .exceptions import DatabaseConnectionError, DatabaseError, QueryTimeoutError, SecurityError, ValidationError
import struct
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

pyodbc.pooling = True

_ALWAYS_BANNED: list[re.Pattern] = [
    re.compile(r"\bxp_\w+", re.IGNORECASE),
    re.compile(r"\bKILL\b", re.IGNORECASE),
    re.compile(r"\bSHUTDOWN\b", re.IGNORECASE),
]

_WRITE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b" + kw + r"\b", re.IGNORECASE)
    for kw in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
               "CREATE", "GRANT", "REVOKE", "DENY", "EXEC", "EXECUTE")
]

_FETCH_BATCH_SIZE: int = getattr(settings, "DB_FETCH_BATCH_SIZE", 500)


def _hash_sql(sql: str) -> str:
    return hashlib.sha256(sql.encode()).hexdigest()[:16]


def _validate_sql(sql: str) -> None:
    if not sql or not sql.strip():
        raise ValidationError("SQL query is empty")

    if len(sql) > settings.MAX_QUERY_LENGTH:
        raise ValidationError(
            f"Query length {len(sql)} exceeds MAX_QUERY_LENGTH={settings.MAX_QUERY_LENGTH}"
        )

    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        raise SecurityError("Multi-statement queries are not permitted")

    for pattern in _ALWAYS_BANNED:
        if pattern.search(sql):
            raise SecurityError(
                f"Query blocked — contains forbidden pattern [{pattern.pattern}] "
                f"| hash={_hash_sql(sql)}"
            )

    if settings.READ_ONLY:
        for pattern in _WRITE_PATTERNS:
            if pattern.search(sql):
                raise SecurityError(
                    f"Query blocked — write operation detected [{pattern.pattern}] "
                    f"in read-only mode | hash={_hash_sql(sql)}"
                )
        if not re.match(r"^\s*SELECT\b", sql, re.IGNORECASE):
            raise SecurityError(
                f"Query blocked — only SELECT is permitted in read-only mode "
                f"| hash={_hash_sql(sql)}"
            )


@contextmanager
def _get_connection():
    conn = None
    try:
        conn = pyodbc.connect(
            settings.MSSQL_CONNECTION_STRING.get_secret_value(),
            autocommit=False,
            timeout=settings.MSSQL_CONNECTION_TIMEOUT,
        )

        # ---------------------------------------------------------
        # CLEAN FIX: Let the MS ODBC Driver handle text natively.
        # Only safely catch datetimeoffset (-155) strings.
        # ---------------------------------------------------------
        def handle_datetimeoffset(dto_value):
            if not dto_value:
                return None

            # If the driver returns the clean SQL string (e.g. '2024-11-11 11:46:35.000 +01:00')
            if isinstance(dto_value, str):
                return dto_value

            # Safe catch for raw bytes without using str() which causes "b'...'"
            if isinstance(dto_value, bytes):
                try:
                    return dto_value.decode('utf-8', errors='ignore').strip('\x00')
                except Exception:
                    pass

            return str(dto_value)

        conn.add_output_converter(-155, handle_datetimeoffset)

        yield conn
    except pyodbc.Error as e:
        logger.error("Connection failed: %s", e)
        raise DatabaseConnectionError(f"Could not connect to database: {e}") from e
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

async def execute_query(
    sql: str,
    params: tuple = (),
    timeout: int | None = None,
    max_rows: int | None = None,
    trace_span: Optional[Any] = None,
    span_name: str = "db_query",
) -> tuple[list[str], list[tuple[Any, ...]]]:
    """
    Validate and execute a SQL query asynchronously.

    Validation runs on the calling thread; the pyodbc call runs in a worker
    thread via asyncio.to_thread() to avoid blocking the event loop.

    Args:
        sql:        Parameterized SQL — use ? placeholders, never f-strings.
        params:     Values for ? placeholders.
        timeout:    Overrides MSSQL_QUERY_TIMEOUT for this call.
        max_rows:   Overrides MAX_ROWS for this call.
        trace_span: Optional Langfuse parent span for child DB span creation.
        span_name:  Label for the child span in the Langfuse waterfall.

    Returns:
        (column_names, rows) — pass to rows_to_dicts() in utils.py

    Raises:
        ValidationError, SecurityError, QueryTimeoutError, DatabaseError
    """
    _validate_sql(sql)

    _timeout = timeout if timeout is not None else settings.MSSQL_QUERY_TIMEOUT
    _max_rows = max_rows if max_rows is not None else settings.MAX_ROWS

    sql_hash = _hash_sql(sql)
    logger.info("Executing query | hash=%s | params_count=%d", sql_hash, len(params))

    def _sync() -> tuple[list[str], list[tuple[Any, ...]]]:
        with _get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, params)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows: list[tuple] = []
                while True:
                    batch = cursor.fetchmany(_FETCH_BATCH_SIZE)
                    if not batch:
                        break
                    rows.extend(tuple(row) for row in batch)
                    if len(rows) >= _max_rows:
                        rows = rows[:_max_rows]
                        logger.warning("Row limit hit — capped at %d | hash=%s", _max_rows, sql_hash)
                        break
                return columns, rows
            except pyodbc.Error as e:
                logger.error("Query failed | hash=%s | error=%s", sql_hash, e)
                raise DatabaseError(f"Query execution failed: {e}") from e
            finally:
                try:
                    cursor.close()
                except (pyodbc.Error, AttributeError):
                    pass

    _tracing = _get_tracing_service()

    try:
        with _tracing.db_span(trace_span, span_name, sql_hash, len(params)) as db_span:
            try:
                columns, rows = await asyncio.wait_for(
                    asyncio.to_thread(_sync),
                    timeout=_timeout,
                )
            except asyncio.TimeoutError:
                logger.error("Query timed out after %ds | hash=%s", _timeout, sql_hash)
                raise QueryTimeoutError(f"Query exceeded {_timeout}s timeout") from None

            logger.info("Query complete | hash=%s | rows=%d", sql_hash, len(rows))
            _tracing.record_db_rows(db_span, len(rows))
            return columns, rows

    except (ValidationError, SecurityError, DatabaseError, QueryTimeoutError):
        raise

    except Exception as e:
        logger.error("Unexpected error | hash=%s | %s", sql_hash, e)
        raise DatabaseError(f"Unexpected database error: {e}") from e


def _get_tracing_service():
    """
    Lazily resolve the TracingService singleton.
    Returns a no-op stub if not yet initialised (e.g. during startup health checks).
    """
    try:
        from src.traksys_mcp.services.langfuse_tracing import get_tracing_service
        instance = get_tracing_service()
        if instance is not None:
            return instance
    except ImportError:
        pass

    class _Stub:
        def db_span(self, *a, **kw):
            from contextlib import contextmanager
            @contextmanager
            def _noop():
                yield object()
            return _noop()

        def record_db_rows(self, *a, **kw):
            pass

    return _Stub()


async def check_connection() -> bool:
    """Verify the database is reachable. Used at server startup."""
    try:
        await execute_query("SELECT 1 AS alive", timeout=5)
        return True
    except Exception as e:
        logger.error("Connection check failed: %s", e)
        return False