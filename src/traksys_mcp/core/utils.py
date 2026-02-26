"""
Serialization helpers for TrakSYS MCP Server.

SQL Server returns types that cannot be JSON-serialized by default.
Every tool passes its rows through these helpers before returning.

Usage:
    from traksys_mcp.utils import serialize_row

    return {"batches": [serialize_row(r) for r in rows], "count": len(rows)}
"""

from datetime import date, datetime, timezone
from typing import Any
import logging

logger = logging.getLogger(__name__)

def serialize_value(value: Any) -> Any:
    """
    Convert a single SQL Server value to a JSON-safe type.

    Handles:
    - datetime / date → ISO 8601 string (converts to UTC)
    - dateTimeOffset → timezone-aware datetime → UTC ISO string
    - bytes / bytearray → placeholder string
    - bool → bool
    - None → None
    """
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, (datetime, date)):
        try:
            # Handle timezone-aware datetimes (datetimeoffset)
            if isinstance(value, datetime) and value.tzinfo is not None:
                # Convert to UTC for consistency
                value = value.astimezone(timezone.utc)
            return value.isoformat()
        except Exception as e:
            logger.warning(f"Failed to serialize datetime {value}: {e}")
            return str(value)

    if isinstance(value, (bytes, bytearray)):
        # Try to decode common SQL Server date/time formats
        try:
            # Attempt to decode as UTF-16-LE (common for SQL Server)
            decoded = value.decode('utf-16-le').strip('\x00')
            # If it looks like an ISO date, parse and format it
            if decoded and decoded[0].isdigit() and ('-' in decoded or 'T' in decoded):
                try:
                    dt = datetime.fromisoformat(decoded.replace('Z', '+00:00'))
                    return dt.isoformat()
                except:
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
    Zip column names and row tuples into a list of dicts, then serialize.

    database.py returns (columns, rows) tuples. Tools need dicts.
    This is the single conversion point — no tool should zip columns manually.

    Example:
        columns = ["batch_id", "start_time"]
        rows    = [(1, datetime(2026, 2, 17, 8, 0))]
        result  = [{"batch_id": 1, "start_time": "2026-02-17T08:00:00"}]
    """
    return [serialize_row(dict(zip(columns, row))) for row in rows]