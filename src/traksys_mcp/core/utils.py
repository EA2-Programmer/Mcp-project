from datetime import date, datetime, timezone
from typing import Any
import logging

logger = logging.getLogger(__name__)


def serialize_value(value: Any) -> Any:
    """Convert a single SQL Server value to a JSON-safe Python type."""
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
            logger.warning(f"Failed to serialize datetime {value}: {e}")
            return str(value)

    if isinstance(value, (bytes, bytearray)):
        try:
            # SQL Server datetimeoffset columns often come back as UTF-16-LE bytes
            decoded = value.decode("utf-16-le").strip("\x00")
            if decoded and decoded[0].isdigit() and ("-" in decoded or "T" in decoded):
                try:
                    return datetime.fromisoformat(decoded.replace("Z", "+00:00")).isoformat()
                except Exception:
                    pass
            return "<binary>"
        except Exception:
            return "<binary>"

    return value


def serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Apply serialize_value to every field in a row dict."""
    return {key: serialize_value(val) for key, val in row.items()}


def rows_to_dicts(columns: list[str], rows: list[tuple]) -> list[dict[str, Any]]:
    """
    Zip column names and row tuples into serialized dicts.
    Single conversion point — no tool should zip columns manually.
    """
    return [serialize_row(dict(zip(columns, row))) for row in rows]