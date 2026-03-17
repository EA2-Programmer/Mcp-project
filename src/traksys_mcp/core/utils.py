from datetime import date, datetime, timezone
from typing import Any
import logging

logger = logging.getLogger(__name__)


def serialize_value(value: Any) -> Any:
    """Convert a single database value to a JSON-serializable Python type."""
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, (datetime, date)):
        try:
            if isinstance(value, datetime) and value.tzinfo is not None:
                value = value.astimezone(timezone.utc)
            return value.isoformat()
        except Exception as e:
            logger.warning("Failed to serialize datetime %s: %s", value, e)
            return str(value)

    if isinstance(value, (bytes, bytearray)):
        return _decode_bytes(value)

    return value


def _decode_bytes(v: bytes | bytearray) -> str | None:
    """
    Decode SQL Server bytes to a clean string.
    nvarchar columns returned via CONVERT() come back as UTF-16-LE bytes.
    """
    try:
        decoded = v.decode("utf-16-le").strip("\x00").strip()
        return decoded if decoded else None
    except (UnicodeDecodeError, ValueError):
        pass
    try:
        decoded = v.decode("utf-8").strip()
        return decoded if decoded else None
    except (UnicodeDecodeError, ValueError):
        pass
    return None


def serialize_row(row: tuple, columns: list) -> dict:
    """
    Convert a single pyodbc row tuple to a serialized dict.
    Applies serialize_value to every field.
    """
    if columns and hasattr(columns[0], "column_name"):
        col_names = [c.column_name for c in columns]
    elif columns and isinstance(columns[0], (list, tuple)):
        col_names = [c[0] for c in columns]
    else:
        col_names = list(columns)

    return {col_names[i]: serialize_value(row[i]) for i in range(len(col_names))}


def rows_to_dicts(columns, rows) -> list[dict]:
    """
    Convert pyodbc cursor results to a list of serialized dicts.
    Handles Column objects, tuples, or plain strings as column descriptors.
    """
    if not rows:
        return []
    return [serialize_row(row, columns) for row in rows]