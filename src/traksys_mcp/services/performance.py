"""
Equipment status and performance analytics service.

Handles real-time machine state, downtime tracking, and OEE metrics.
"""

import logging
from typing import Optional, List, Any
from src.traksys_mcp.core.database import execute_query
from src.traksys_mcp.core.utils import rows_to_dicts
from src.traksys_mcp.services.time_resolution import TimeResolutionService

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
        time_service: Optional[TimeResolutionService] = None
) -> dict:
    """
    Retrieve equipment status, OEE, and real-time tag data.
    """
    # 1. Resolve system_name to ID if needed
    if system_name and system_id is None:
        sql_lookup = "SELECT TOP 1 ID FROM tSystem WHERE Name = ? OR AltName = ? OR ExternalID = ?"
        _, rows = await execute_query(sql_lookup, (system_name, system_name, system_name))
        if rows:
            system_id = rows[0][0]
            logger.info(f"Resolved system_name '{system_name}' → ID {system_id}")
        else:
            return {
                "equipment": [],
                "message": f"No equipment found with name '{system_name}'"
            }

    # 2. Resolve Time
    time_info = None
    actual_start = start_date
    actual_end = end_date

    if (time_window or start_date) and time_service:
        resolution = await time_service.resolve(time_window or "", table="tJobSystemActual")
        time_info = resolution
        actual_start = resolution["actual"]["start"]
        actual_end = resolution["actual"]["end"]

    # 3. Base Query - Equipment Info + Current State
    where_parts = ["s.Enabled = 1"]
    params = []

    if system_id:
        where_parts.append("s.ID = ?")
        params.append(system_id)
    if area_id:
        where_parts.append("s.AreaID = ?")
        params.append(area_id)

    where_clause = " AND ".join(where_parts)

    # Join with tJobSystemActual for current activity (open records)
    # Join with tTag for live values if requested
    tag_columns = ""
    tag_joins = ""
    if include_tags:
        tag_columns = """,
            t_act.Value AS actual_count, t_act.Units AS count_units,
            t_prod.Value AS current_product,
            t_batch.Value AS current_batch,
            t_plan.Value AS planned_count
        """
        tag_joins = """
            LEFT JOIN tTag t_act ON s.ActualSizeTagID = t_act.ID
            LEFT JOIN tTag t_prod ON s.ProductTagID = t_prod.ID
            LEFT JOIN tTag t_batch ON s.BatchTagID = t_batch.ID
            LEFT JOIN tTag t_plan ON s.PlannedSizeTagID = t_plan.ID
        """

    sql = f"""
        SELECT TOP {limit}
            s.ID AS system_id,
            s.Name AS system_name,
            s.Description,
            s.AreaID,
            jsa.JobID AS current_job_id,
            jsa.StartDateTime AS session_start,
            CASE WHEN jsa.ID IS NOT NULL THEN 'Running' ELSE 'Idle' END AS status
            {tag_columns}
        FROM tSystem s
        LEFT JOIN tJobSystemActual jsa 
            ON s.ID = jsa.SystemID 
            AND jsa.EndDateTime IS NULL
        {tag_joins}
        WHERE {where_clause}
        ORDER BY s.DisplayOrder
    """

    columns, rows = await execute_query(sql, tuple(params))
    equipment_data = rows_to_dicts(columns, rows)

    # 4. OEE / Performance Calculation (if requested and time range provided)
    if include_oee and actual_start and actual_end:
        for equip in equipment_data:
            sid = equip["system_id"]
            # Calculate metrics for this system in this period
            perf_sql = """
                SELECT 
                    SUM(DATEDIFF(MINUTE, StartDateTime, ISNULL(EndDateTime, GETDATE()))) AS total_runtime_mins,
                    COUNT(ID) AS session_count
                FROM tJobSystemActual
                WHERE SystemID = ? 
                AND StartDateTime >= ? 
                AND (EndDateTime <= ? OR EndDateTime IS NULL)
            """
            _, perf_rows = await execute_query(perf_sql, (sid, actual_start, actual_end))
            if perf_rows and perf_rows[0][0]:
                equip["performance_metrics"] = {
                    "total_runtime_minutes": perf_rows[0][0],
                    "session_count": perf_rows[0][1],
                    "period_start": actual_start,
                    "period_end": actual_end
                }

    result = {
        "equipment": equipment_data,
        "count": len(equipment_data)
    }

    if time_info:
        result["time_info"] = time_info

    return result
