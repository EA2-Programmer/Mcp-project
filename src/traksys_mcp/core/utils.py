"""
Serialization utilities for database results.

Converts pyodbc rows → JSON-serializable dicts with proper type handling.
Ensures datetime, bytes, and other non-serializable types are properly converted.
"""

from datetime import date, datetime, timezone
from typing import Any
import logging

logger = logging.getLogger(__name__)


def serialize_value(value: Any) -> Any:
    """
    Convert a single database value to a JSON-serializable Python type.

    Handles:
    - None, bool, int, float, str → pass-through
    - datetime/date → ISO 8601 string (UTC-normalized)
    - bytes/bytearray → decode as UTF-16-LE (SQL Server text) or hex fallback
    - Unexpected types → string conversion with warning
    """
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value

    # Datetime handling: normalize to UTC ISO format
    if isinstance(value, datetime):
        try:
            if value.tzinfo is None:
                # Assume UTC if naive (adjust if your DB uses local time)
                value = value.replace(tzinfo=timezone.utc)
            else:
                value = value.astimezone(timezone.utc)
            return value.isoformat()
        except Exception as e:
            logger.warning("Failed to serialize datetime %r: %s", value, e)
            return str(value)

    if isinstance(value, date):
        try:
            return value.isoformat()
        except Exception as e:
            logger.warning("Failed to serialize date %r: %s", value, e)
            return str(value)

    # Bytes handling: try UTF-16-LE (SQL Server nvarchar), then UTF-8, then hex
    if isinstance(value, (bytes, bytearray)):
        return _decode_bytes(value)

    # Fallback for unexpected types (e.g., Decimal, UUID, memoryview)
    try:
        return str(value)
    except Exception as e:
        logger.error("Failed to serialize value of type %s: %s", type(value).__name__, e)
        return None


def _decode_bytes(v: bytes | bytearray) -> str | None:
    """
    Decode SQL Server bytes to string.

    Priority:
    1. UTF-16-LE (native for nvarchar/nchar)
    2. UTF-8 (legacy/misconfigured columns)
    3. Hex representation (for true binary data like images, uniqueidentifiers)
    """
    if not v:
        return None

    for encoding in ("utf-16-le", "utf-8"):
        try:
            decoded = v.decode(encoding).rstrip("\x00").strip()
            return decoded if decoded else None
        except (UnicodeDecodeError, ValueError):
            continue

    # Last resort: hex representation for true binary data
    logger.debug("Returning hex for undecodable bytes: %r", v[:20])
    return v.hex()


def serialize_row(row: tuple, columns: list) -> dict:
    """Convert a single pyodbc row to a serialized dict."""
    # Extract column names from various descriptor formats
    if not columns:
        col_names = [f"col_{i}" for i in range(len(row))]
    elif hasattr(columns[0], "column_name"):  # SQLAlchemy-style
        col_names = [c.column_name for c in columns]
    elif isinstance(columns[0], (list, tuple)):  # pyodbc description
        col_names = [c[0] for c in columns]
    else:  # Plain list of strings
        col_names = list(columns)

    return {
        col_names[i]: serialize_value(row[i])
        for i in range(min(len(col_names), len(row)))
    }


def rows_to_dicts(columns: list, rows: list[tuple]) -> list[dict]:
    """Convert pyodbc cursor results to list of serialized dicts."""
    if not rows:
        return []
    return [serialize_row(row, columns) for row in rows]