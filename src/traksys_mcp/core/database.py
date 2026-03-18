"""
Database connection and query execution module for TrakSYS MCP.

This module provides a secure, async-compatible interface to SQL Server with:
- Connection pooling and automatic converter registration
- SQL injection prevention and query validation
- Centralized UTF-16-LE decoding for all text columns
- Proper datetime handling for SQL Server types
- Langfuse tracing integration
- Read-only mode enforcement
"""

import asyncio
import hashlib
import logging
import re
from contextlib import contextmanager
from datetime import datetime, date, timezone
from typing import Any, Optional, Tuple, List, Dict

import pyodbc

from src.traksys_mcp.config.setting import settings
from .exceptions import DatabaseConnectionError, DatabaseError, QueryTimeoutError, SecurityError, ValidationError

logger = logging.getLogger(__name__)

# Enable connection pooling for better performance
pyodbc.pooling = True

# Security patterns - always blocked regardless of mode
_ALWAYS_BANNED: List[re.Pattern] = [
    re.compile(r"\bxp_\w+", re.IGNORECASE),  # Extended stored procedures
    re.compile(r"\bKILL\b", re.IGNORECASE),  # Kill connection
    re.compile(r"\bSHUTDOWN\b", re.IGNORECASE),  # Shutdown server
]

# Write operation patterns - blocked in read-only mode
_WRITE_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b" + kw + r"\b", re.IGNORECASE)
    for kw in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
               "CREATE", "GRANT", "REVOKE", "DENY", "EXEC", "EXECUTE")
]

# Batch size for fetching rows to avoid memory issues
_FETCH_BATCH_SIZE: int = getattr(settings, "DB_FETCH_BATCH_SIZE", 500)

# SQL Server type codes for output converters
# Reference: https://docs.microsoft.com/en-us/sql/odbc/reference/appendixes/sql-data-types
SQL_TYPE_CODES = {
    'NVARCHAR': -9,
    'NVARCHAR_MAX': -10,
    'NCHAR': -8,
    'TEXT': -1,  # Legacy
    'DATETIMEOFFSET': -155,
    'DATETIME2': -150,
    'DATETIME': -151,  # Legacy
}


def _hash_sql(sql: str) -> str:
    """
    Generate a short hash of SQL for logging and tracking.

    Args:
        sql: SQL query string

    Returns:
        First 16 chars of SHA256 hash
    """
    return hashlib.sha256(sql.encode()).hexdigest()[:16]


def _validate_sql(sql: str) -> None:
    """
    Validate SQL query for security and compliance.

    Performs multiple checks:
    - Empty query validation
    - Length limits
    - Multi-statement prevention
    - Blocked pattern detection
    - Read-only mode enforcement

    Args:
        sql: SQL query to validate

    Raises:
        ValidationError: If query is empty or too long
        SecurityError: If query contains forbidden patterns or write operations in read-only mode
    """
    if not sql or not sql.strip():
        raise ValidationError("SQL query is empty")

    if len(sql) > settings.MAX_QUERY_LENGTH:
        raise ValidationError(
            f"Query length {len(sql)} exceeds MAX_QUERY_LENGTH={settings.MAX_QUERY_LENGTH}"
        )

    # Prevent multi-statement queries (SQL injection risk)
    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        raise SecurityError(
            f"Multi-statement queries are not permitted | hash={_hash_sql(sql)}"
        )

    # Check for always-banned patterns
    for pattern in _ALWAYS_BANNED:
        if pattern.search(sql):
            raise SecurityError(
                f"Query blocked — contains forbidden pattern [{pattern.pattern}] "
                f"| hash={_hash_sql(sql)}"
            )

    # In read-only mode, enforce additional restrictions
    if settings.READ_ONLY:
        # Check for write operations
        for pattern in _WRITE_PATTERNS:
            if pattern.search(sql):
                raise SecurityError(
                    f"Query blocked — write operation detected [{pattern.pattern}] "
                    f"in read-only mode | hash={_hash_sql(sql)}"
                )

        # Ensure it's a SELECT query
        if not re.match(r"^\s*SELECT\b", sql, re.IGNORECASE):
            raise SecurityError(
                f"Query blocked — only SELECT is permitted in read-only mode "
                f"| hash={_hash_sql(sql)}"
            )


def _decode_sql_server_bytes(value: bytes | bytearray) -> str | None:
    """
    Decode SQL Server bytes to a clean string.

    SQL Server nvarchar/nchar columns are returned as UTF-16-LE bytes.
    This function attempts to decode them properly and returns None if decoding fails.

    Args:
        value: Bytes or bytearray from SQL Server

    Returns:
        Decoded string or None if decoding fails
    """
    if value is None:
        return None

    # Try UTF-16-LE first (SQL Server's native encoding for nvarchar)
    try:
        decoded = value.decode("utf-16-le").strip("\x00").strip()
        return decoded if decoded else None
    except (UnicodeDecodeError, ValueError):
        pass

    # Fallback to UTF-8 for legacy or misconfigured columns
    try:
        decoded = value.decode("utf-8").strip()
        return decoded if decoded else None
    except (UnicodeDecodeError, ValueError):
        pass

    # If all decoding fails, log and return None
    logger.debug(f"Failed to decode bytes: {value[:50]}...")
    return None


def _handle_nvarchar(value: Any) -> Any:
    """
    Output converter for SQL Server nvarchar/nchar/text columns.

    This converter is registered with pyodbc to automatically decode
    all text columns to Python strings.

    Args:
        value: Raw value from SQL Server (bytes, str, or None)

    Returns:
        Properly decoded string or original value if not bytes
    """
    if value is None:
        return None

    # If it's already a string, return as-is
    if isinstance(value, str):
        return value

    # Decode bytes to string
    if isinstance(value, (bytes, bytearray)):
        return _decode_sql_server_bytes(value)

    # Return anything else as-is
    return value


def _handle_datetimeoffset(value: Any) -> Any:
    """
    Output converter for SQL Server datetimeoffset/datetime2/datetime columns.

    Converts SQL Server datetime values to Python datetime objects.
    Handles both bytes and already-converted values.

    Args:
        value: Raw value from SQL Server

    Returns:
        Python datetime object or string if parsing fails
    """
    if value is None:
        return None

    # If it's already a datetime/date, return as-is (from another converter)
    if isinstance(value, (datetime, date)):
        return value

    # SQL Server datetime values often come as bytes
    if isinstance(value, (bytes, bytearray)):
        try:
            # Decode as UTF-16-LE first
            decoded = value.decode('utf-16-le').strip('\x00')

            # Parse the datetime string if it contains digits
            if decoded and any(c.isdigit() for c in decoded):
                # Handle ISO format with T separator
                if 'T' in decoded:
                    # Replace Z with +00:00 for UTC
                    return datetime.fromisoformat(decoded.replace('Z', '+00:00'))

                # Handle SQL Server format: YYYY-MM-DD HH:MM:SS.nnnnnnn +HH:MM
                elif ' ' in decoded and ('+' in decoded or '-' in decoded[19:]):
                    # Replace space with T for ISO format
                    return datetime.fromisoformat(decoded.replace(' ', 'T'))
        except (UnicodeDecodeError, ValueError, TypeError) as e:
            logger.debug(f"Failed to decode datetimeoffset: {e}")

    # Return as string if we can't parse (better than crashing)
    return str(value)


@contextmanager
def _get_connection():
    """
    Context manager for database connections.

    Establishes a connection to SQL Server with:
    - Connection pooling enabled
    - Proper timeout settings
    - Output converters for all relevant SQL types
    - Automatic connection cleanup

    Yields:
        Active pyodbc connection object

    Raises:
        DatabaseConnectionError: If connection fails
    """
    conn = None
    try:
        # Establish connection
        conn = pyodbc.connect(
            settings.MSSQL_CONNECTION_STRING.get_secret_value(),
            autocommit=False,
            timeout=settings.MSSQL_CONNECTION_TIMEOUT,
        )

        # =====================================================
        # OUTPUT CONVERTERS - CENTRALIZED FIX FOR ALL ENCODING ISSUES
        # =====================================================

        # Register nvarchar/nchar/text converters (handles all text columns)
        conn.add_output_converter(SQL_TYPE_CODES['NVARCHAR'], _handle_nvarchar)  # nvarchar
        conn.add_output_converter(SQL_TYPE_CODES['NVARCHAR_MAX'], _handle_nvarchar)  # nvarchar(max)
        conn.add_output_converter(SQL_TYPE_CODES['NCHAR'], _handle_nvarchar)  # nchar
        conn.add_output_converter(SQL_TYPE_CODES['TEXT'], _handle_nvarchar)  # text (legacy)

        # Register datetime converters
        conn.add_output_converter(SQL_TYPE_CODES['DATETIMEOFFSET'], _handle_datetimeoffset)  # datetimeoffset
        conn.add_output_converter(SQL_TYPE_CODES['DATETIME2'], _handle_datetimeoffset)  # datetime2
        conn.add_output_converter(SQL_TYPE_CODES['DATETIME'], _handle_datetimeoffset)  # datetime (legacy)

        # Note: We do NOT register type code -9 for datetime because -9 is nvarchar!
        # The previous code that registered -9 for datetime was incorrect.

        logger.debug("Database connection established with output converters")
        yield conn

    except pyodbc.Error as e:
        logger.error("Connection failed: %s", e)
        raise DatabaseConnectionError(f"Could not connect to database: {e}") from e
    finally:
        if conn:
            try:
                conn.close()
                logger.debug("Database connection closed")
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

    This is the primary database interface for the application. It:
    1. Validates the SQL for security
    2. Executes in a thread pool to avoid blocking the event loop
    3. Applies timeout and row limits
    4. Integrates with Langfuse tracing
    5. Returns column names and rows for further processing

    Args:
        sql: Parameterized SQL query with ? placeholders
        params: Tuple of values for ? placeholders
        timeout: Query timeout in seconds (overrides default)
        max_rows: Maximum rows to return (overrides default)
        trace_span: Optional Langfuse parent span for tracing
        span_name: Name for the tracing span

    Returns:
        Tuple of (column_names, rows) where:
            column_names: List of column names as strings
            rows: List of tuples containing row data

    Raises:
        ValidationError: If SQL validation fails
        SecurityError: If security checks fail
        QueryTimeoutError: If query exceeds timeout
        DatabaseError: For other database errors

    """
    # Validate SQL before execution
    _validate_sql(sql)

    # Apply defaults
    _timeout = timeout if timeout is not None else settings.MSSQL_QUERY_TIMEOUT
    _max_rows = max_rows if max_rows is not None else settings.MAX_ROWS

    # Generate hash for logging
    sql_hash = _hash_sql(sql)
    logger.info("Executing query | hash=%s | params_count=%d", sql_hash, len(params))

    def _sync() -> tuple[list[str], list[tuple[Any, ...]]]:
        """
        Synchronous query execution function.
        Runs in a thread pool to avoid blocking the event loop.
        """
        with _get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Execute query with parameters
                cursor.execute(sql, params)

                # Get column names
                columns = [desc[0] for desc in cursor.description] if cursor.description else []

                # Fetch rows in batches to manage memory
                rows: list[tuple] = []
                while True:
                    batch = cursor.fetchmany(_FETCH_BATCH_SIZE)
                    if not batch:
                        break
                    rows.extend(tuple(row) for row in batch)

                    # Enforce row limit
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

    # Get tracing service
    _tracing = _get_tracing_service()

    try:
        # Execute in thread pool with timeout and tracing
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
        # Re-raise known exceptions
        raise

    except Exception as e:
        logger.error("Unexpected error | hash=%s | %s", sql_hash, e)
        raise DatabaseError(f"Unexpected database error: {e}") from e


def _get_tracing_service():
    """
    Lazily resolve the TracingService singleton.

    Returns a no-op stub if not yet initialized (e.g., during startup health checks)
    to avoid circular imports and allow graceful degradation.
    """
    try:
        from src.traksys_mcp.services.tracing import _tracing_service_instance
        if _tracing_service_instance is not None:
            return _tracing_service_instance
    except ImportError:
        pass

    # No-op stub for when tracing isn't available
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
    """
    Verify database connectivity.

    Executes a simple query to ensure the database is reachable.
    Used during server startup and health checks.

    Returns:
        True if database is reachable, False otherwise
    """
    try:
        await execute_query("SELECT 1 AS alive", timeout=5)
        logger.info("Database connection check successful")
        return True
    except Exception as e:
        logger.error("Connection check failed: %s", e)
        return False