import logging
from typing import Optional, Any

from src.traksys_mcp.core.database import execute_query
from src.traksys_mcp.core.utils import rows_to_dicts
from src.traksys_mcp.services.time_resolution import TimeResolutionService
from src.traksys_mcp.utils.performance_queries import (
    SYSTEM_NAME_LOOKUP,
    OEE_METRICS,
    build_equipment_state_query,
)

logger = logging.getLogger(__name__)


async def get_equipment_state(
    system_id: Optional[int] = None,
    system_name: Optional[str] = None,
    area_id: Optional[int] = None,
    time_window: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_oee: bool = False,
    include_tags: bool = False,
    limit: int = 50,
    time_service: Optional[TimeResolutionService] = None,
    trace_span=None,
) -> dict:
    """Retrieve equipment status, OEE metrics, and optional real-time tag data."""
    if system_name and system_id is None:
        _, rows = await execute_query(
            SYSTEM_NAME_LOOKUP,
            (system_name, system_name, system_name),
            trace_span=trace_span,
            span_name="system_name_lookup",
        )
        if rows:
            system_id = rows[0][0]
            logger.info("Resolved system_name '%s' → ID %s", system_name, system_id)
        else:
            return {"equipment": [], "message": f"No equipment found with name '{system_name}'"}

    time_info = None
    actual_start = start_date
    actual_end = end_date

    if time_window and time_service and not (start_date and end_date):
        resolution = await time_service.resolve(time_window, table="tJobSystemActual")
        time_info = resolution
        actual_start = resolution["actual"]["start"]
        actual_end = resolution["actual"]["end"]
    elif start_date and end_date:
        logger.info("Using explicit date range: %s to %s", start_date, end_date)
        pass

    where_parts = ["s.Enabled = 1", "s.IsTemplate = 0"]
    params = []

    if system_id:
        where_parts.append("s.ID = ?")
        params.append(system_id)
    if area_id:
        where_parts.append("s.AreaID = ?")
        params.append(area_id)

    where_clause = " AND ".join(where_parts)

    columns, rows = await execute_query(
        build_equipment_state_query(limit, where_clause, include_tags),
        tuple(params),
        trace_span=trace_span,
        span_name="equipment_state_query",
    )
    equipment_data = rows_to_dicts(columns, rows)

    if include_oee and actual_start and actual_end:
        for equip in equipment_data:
            sid = equip["system_id"]
            _, perf_rows = await execute_query(
                OEE_METRICS,
                (sid, actual_start, actual_end),
                trace_span=trace_span,
                span_name=f"oee_metrics_system_{sid}",
            )
            if perf_rows and perf_rows[0][0]:
                equip["performance_metrics"] = {
                    "total_runtime_minutes": perf_rows[0][0],
                    "session_count": perf_rows[0][1],
                    "period_start": actual_start,
                    "period_end": actual_end,
                }

    result: dict[str, Any] = {"equipment": equipment_data, "count": len(equipment_data)}
    if time_info:
        result["time_info"] = time_info
    return result