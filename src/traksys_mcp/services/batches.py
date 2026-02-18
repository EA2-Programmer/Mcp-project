"""
Batch data queries with intelligent time handling.

Uses correct column names from actual EBR_Template schema.
"""

from traksys_mcp.core.database import execute_query
from traksys_mcp.core.utils import rows_to_dicts
from traksys_mcp.services.time_resolution import TimeResolutionService
from typing import Optional
import logging

logger = logging.getLogger(__name__)


async def get_batches(
        batch_id: Optional[int] = None,
        system_id: Optional[int] = None,
        job_id: Optional[int] = None,
        time_window: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        state: Optional[int] = None,
        limit: int = 50,
        time_service: Optional[TimeResolutionService] = None
) -> dict:
    """
    Query batches with intelligent time handling.

    Args:
        batch_id: Specific batch ID (tBatch.ID)
        system_id: System/Line ID (tBatch.SystemID)
        job_id: Job ID (tBatch.JobID)
        time_window: Natural language time (e.g., "yesterday", "last 7 days")
        start_date: Explicit start date (ISO format)
        end_date: Explicit end date (ISO format)
        state: Batch state filter (tBatch.State - integer)
        limit: Max rows
        time_service: TimeResolutionService instance (optional)

    Returns:
        {
            "batches": [...],
            "count": int,
            "time_info": {...} or None
        }
    """
    time_info = None
    actual_start = start_date
    actual_end = end_date

    # If time_window provided and time_service available, resolve it
    if time_window and time_service:
        resolution = await time_service.resolve(time_window, table="tBatch")
        time_info = resolution

        # Use the actual dates (potentially fallback dates)
        actual_start = resolution["actual"]["start"].split("T")[0]
        actual_end = resolution["actual"]["end"].split("T")[0]

    # Build WHERE clause dynamically
    where_parts = []
    params = []

    if batch_id is not None:
        where_parts.append("b.ID = ?")
        params.append(batch_id)

    if system_id is not None:
        where_parts.append("b.SystemID = ?")
        params.append(system_id)

    if job_id is not None:
        where_parts.append("b.JobID = ?")
        params.append(job_id)

    if actual_start:
        where_parts.append("b.StartDateTime >= ?")
        params.append(actual_start)

    if actual_end:
        where_parts.append("b.EndDateTime <= ?")
        params.append(actual_end)

    if state is not None:
        where_parts.append("b.State = ?")
        params.append(state)

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"

    # SQL using CORRECT column names from your schema
    sql = f"""
        SELECT TOP {limit}
            b.ID,
            b.Name,
            b.AltName,
            b.SystemID,
            b.JobID,
            b.Lot,
            b.SubLot,
            b.State,
            CAST(b.StartDateTime AS datetime) AS StartDateTime,
            CAST(b.EndDateTime AS datetime) AS EndDateTime,
            b.Date,
            b.PlannedBatchSize,
            b.ActualBatchSize,
            b.[User],
            j.Name AS JobName,
            j.ExternalID AS JobExternalID,
            p.Name AS ProductName,
            p.Description AS ProductDescription,
            s.Name AS SystemName
        FROM tBatch b
        LEFT JOIN tJob j ON b.JobID = j.ID
        LEFT JOIN tProduct p ON j.ProductID = p.ID
        LEFT JOIN tSystem s ON b.SystemID = s.ID
        WHERE {where_clause}
        ORDER BY b.StartDateTime DESC
    """

    columns, rows = await execute_query(sql, tuple(params))
    batches = rows_to_dicts(columns, rows)

    result = {
        "batches": batches,
        "count": len(batches)
    }

    if time_info:
        result["time_info"] = time_info

    return result