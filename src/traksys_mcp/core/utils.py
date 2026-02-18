"""
Serialization helpers for TrakSYS MCP Server.

SQL Server returns types that cannot be JSON-serialized by default.
Every tool passes its rows through these helpers before returning.

Usage:
    from traksys_mcp.utils import serialize_row

    return {"batches": [serialize_row(r) for r in rows], "count": len(rows)}
"""

from datetime import date, datetime
from typing import Any


def serialize_value(value: Any) -> Any:
    """
    Convert a single SQL Server value to a JSON-safe type.

    Handles the types pyodbc returns that standard json.dumps() rejects:
    - datetime / date  → ISO 8601 string
    - bytes / bytearray → placeholder string (binary blobs are not useful to LLMs)
    - bool             → bool (must be checked BEFORE int — bool is a subclass of int)
    - None             → None (pass through, JSON null)
    - everything else  → returned as-is
    """
    if value is None:
        return None
    if isinstance(value, bool):          # before int — bool subclasses int
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
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