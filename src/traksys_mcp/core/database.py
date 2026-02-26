"""
Database layer for the TrakSYS MCP Server.

Bridges synchronous pyodbc with async FastMCP using asyncio.to_thread().
All queries pass through a single validation gate before execution.

Every tool imports execute_query() — nothing else touches pyodbc directly.
"""

import asyncio
import hashlib
import logging
import re
from contextlib import contextmanager
from typing import Any

import pyodbc

from src.traksys_mcp.config.setting import settings
from .exceptions import DatabaseConnectionError, DatabaseError, QueryTimeoutError, SecurityError, ValidationError

logger = logging.getLogger(__name__)

# ODBC connection pooling — reuses connections across calls instead of
# opening a new TCP connection on every query
pyodbc.pooling = True


# ---------------------------------------------------------------------------
# SQL Validation
# ---------------------------------------------------------------------------

# Blocked regardless of READ_ONLY setting — these are always dangerous
_ALWAYS_BANNED: list[re.Pattern] = [
    re.compile(r"\bxp_\w+", re.IGNORECASE),     # extended stored procedures
    re.compile(r"\bKILL\b", re.IGNORECASE),
    re.compile(r"\bSHUTDOWN\b", re.IGNORECASE),
]

# Blocked when READ_ONLY=true
_WRITE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b" + kw + r"\b", re.IGNORECASE)
    for kw in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
               "CREATE", "GRANT", "REVOKE", "DENY", "EXEC", "EXECUTE")
]


def _hash_sql(sql: str) -> str:
    """Return a short SHA-256 hash of the SQL for safe log references."""
    return hashlib.sha256(sql.encode()).hexdigest()[:16]


def _validate_sql(sql: str) -> None:
    """
    Run all security checks against a SQL string.

    Raises ValidationError or SecurityError — never returns a value.
    Called before any thread is spawned so blocked queries fail instantly.
    """
    if not sql or not sql.strip():
        raise ValidationError("SQL query is empty")

    if len(sql) > settings.MAX_QUERY_LENGTH:
        raise ValidationError(
            f"Query length {len(sql)} exceeds MAX_QUERY_LENGTH={settings.MAX_QUERY_LENGTH}"
        )

    # Multi-statement check — semicolon anywhere except trailing
    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        raise SecurityError("Multi-statement queries are not permitted")

    # Always-banned patterns
    for pattern in _ALWAYS_BANNED:
        if pattern.search(sql):
            raise SecurityError(
                f"Query blocked — contains forbidden pattern [{pattern.pattern}] "
                f"| hash={_hash_sql(sql)}"
            )

    # Read-only enforcement
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


# ---------------------------------------------------------------------------
# Connection Management
# ---------------------------------------------------------------------------

@contextmanager
def _get_connection():
    """
    Open a pyodbc connection and guarantee cleanup on exit.

    Uses a context manager so the connection closes even if the
    query raises an exception mid-execution.
    """
    conn = None
    try:
        conn = pyodbc.connect(
            settings.MSSQL_CONNECTION_STRING.get_secret_value(),
            autocommit=False,
            timeout=settings.MSSQL_CONNECTION_TIMEOUT,
        )
        conn.add_output_converter(-155, lambda raw: raw.decode("utf-16-le"))
        yield conn
    except pyodbc.Error as e:
        logger.error("Connection failed: %s", e) # we should revisit here to ensure password are not logged
        raise DatabaseConnectionError(f"Could not connect to database: {e}") from e
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Query Execution
# ---------------------------------------------------------------------------

async def execute_query(
    sql: str,
    params: tuple = (),
    timeout: int | None = None,
    max_rows: int | None = None,
) -> tuple[list[str], list[tuple[Any, ...]]]:
    """
    Validate and execute a SQL SELECT query asynchronously.

    Validation runs on the calling thread (fast, no DB needed).
    The actual pyodbc call runs in a worker thread via asyncio.to_thread()
    so it never blocks the event loop.

    Args:
        sql:      Parameterized SQL string — use ? placeholders, never f-strings
        params:   Values for the ? placeholders
        timeout:  Override MSSQL_QUERY_TIMEOUT for this call
        max_rows: Override MAX_ROWS for this call

    Returns:
        (column_names, rows) — pass to rows_to_dicts() in utils.py

    Raises:
        ValidationError:    Empty SQL, too long, multi-statement
        SecurityError:      Banned keywords, write in read-only mode
        QueryTimeoutError:  Query exceeded timeout
        DatabaseError:      Any other pyodbc failure
    """
    _validate_sql(sql)  # fail fast — before any thread is spawned

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
                    FETCH_BATCH_SIZE = getattr(settings, 'DB_FETCH_BATCH_SIZE', 500)
                    batch = cursor.fetchmany(FETCH_BATCH_SIZE)
                    if not batch:
                        break
                    rows.extend(batch)
                    if len(rows) >= _max_rows:
                        rows = rows[:_max_rows]
                        logger.warning(
                            "Row limit hit — capped at %d | hash=%s", _max_rows, sql_hash
                        )
                        break
                return columns, rows
            except pyodbc.Error as e:
                logger.error("Query failed | hash=%s | error=%s", sql_hash, e)
                raise DatabaseError(f"Query execution failed: {e}") from e
            finally:
                try:
                    cursor.close()
                except Exception:
                    pass

    try:
        columns, rows = await asyncio.wait_for(
            asyncio.to_thread(_sync),
            timeout=_timeout,
        )
        logger.info("Query complete | hash=%s | rows=%d", sql_hash, len(rows))
        return columns, rows

    except asyncio.TimeoutError:
        logger.error("Query timed out after %ds | hash=%s", _timeout, sql_hash)
        raise QueryTimeoutError(f"Query exceeded {_timeout}s timeout") from None

    except (ValidationError, SecurityError, DatabaseError, QueryTimeoutError):
        raise  # already typed, let them propagate as-is

    except Exception as e:
        logger.error("Unexpected error | hash=%s | %s", sql_hash, e)
        raise DatabaseError(f"Unexpected database error: {e}") from e


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

async def check_connection() -> bool:
    """Verify the database is reachable. Used at server startup."""
    try:
        await execute_query("SELECT 1 AS alive", timeout=5)
        return True
    except Exception as e:
        logger.error("Connection check failed: %s", e)
        return False