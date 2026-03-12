"""
OEE data queries with proxy calculation.
Follows OEE Tool Design Document.
"""

import logging
from typing import Any, Dict

from src.traksys_mcp.core.database import execute_query
from src.traksys_mcp.core.utils import rows_to_dicts
from src.traksys_mcp.services.time_resolution import TimeResolutionService

logger = logging.getLogger(__name__)


async def calculate_oee(
    line: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    granularity: str = "daily",
    breakdown: bool = True,
    time_service: TimeResolutionService | None = None,
) -> Dict[str, Any]:
    """Calculate OEE or proxy based on available data."""
    if not start_date or not end_date:
        raise ValueError("start_date and end_date are required")

    system_id = None
    if line:
        sql_lookup = "SELECT TOP 1 ID FROM tSystem WHERE Name = ? OR AltName = ?"
        _, rows = await execute_query(sql_lookup, (line, line))
        if rows:
            system_id = rows[0][0]
        else:
            return {
                "oee": {
                    "line": line,
                    "date_range": {"start": start_date, "end": end_date},
                    "data_source": "none",
                    "oee_available": False,
                    "oee_message": f"No system found with name '{line}'",
                }
            }

    # Step 1: Check for real OEE data
    where_parts = ["oi.StartDateTime >= ?", "oi.StartDateTime < ?"]
    params = [start_date, end_date]
    if system_id:
        where_parts.append("oi.SystemID = ?")
        params.append(system_id)

    sql_check = f"SELECT COUNT(*) FROM tOeeInterval oi WHERE {' AND '.join(where_parts)}"
    _, rows = await execute_query(sql_check, tuple(params))
    has_real_data = rows[0][0] > 0

    if has_real_data:
        data = await _get_real_oee(system_id, start_date, end_date, granularity, breakdown)
    else:
        data = await _get_proxy_oee(system_id, start_date, end_date, granularity, breakdown)

    return {"oee": data}


async def _get_real_oee(system_id, start_date, end_date, granularity, breakdown) -> Dict[str, Any]:
    group_by = ""
    select_extra = ""
    order_extra = "line"

    if granularity == "daily":
        select_extra = ", CAST(oi.StartDateTime AS DATE) AS production_date"
        group_by = "GROUP BY s.Name, CAST(oi.StartDateTime AS DATE)"
        order_extra = "production_date"
    elif granularity == "weekly":
        select_extra = ", DATEPART(week, oi.StartDateTime) AS production_week"
        group_by = "GROUP BY s.Name, DATEPART(week, oi.StartDateTime)"
        order_extra = "production_week"
    elif granularity == "shift":
        select_extra = ", sh.Name AS shift_name"
        group_by = "GROUP BY s.Name, sh.Name"
        order_extra = "shift_name"
    else:
        group_by = "GROUP BY s.Name"

    where_parts = ["oi.StartDateTime >= ?", "oi.StartDateTime < ?"]
    params = [start_date, end_date]
    if system_id:
        where_parts.append("oi.SystemID = ?")
        params.append(system_id)

    sql = f"""
        SELECT 
            s.Name AS line{select_extra},
            SUM(oi.PlannedProductionTime) AS total_planned_seconds,
            SUM(oi.AvailabilityLossSeconds) AS total_downtime_seconds,
            (SUM(oi.PlannedProductionTime) - SUM(oi.AvailabilityLossSeconds)) * 100.0 / 
                NULLIF(SUM(oi.PlannedProductionTime), 0) AS availability_pct,
            SUM(oi.GoodCalculationUnitsCount) AS good_units,
            SUM(oi.TotalCalculationUnitsCount) AS total_units,
            SUM(oi.GoodCalculationUnitsCount) * 100.0 / 
                NULLIF(SUM(oi.TotalCalculationUnitsCount), 0) AS quality_pct,
            (SUM(oi.PlannedProductionTime) - SUM(oi.AvailabilityLossSeconds)) * 1.0 / 
                NULLIF(SUM(oi.PlannedProductionTime), 0) 
            * SUM(oi.GoodCalculationUnitsCount) * 1.0 / 
                NULLIF(SUM(oi.TotalCalculationUnitsCount), 0) * 100 AS oee_pct
        FROM tOeeInterval oi
        JOIN tSystem s ON oi.SystemID = s.ID AND s.IsTemplate = 0
        LEFT JOIN tShiftHistory sh ON oi.ShiftHistoryID = sh.ID
        WHERE {' AND '.join(where_parts)}
        {group_by}
        ORDER BY {order_extra}
    """
    columns, rows = await execute_query(sql, tuple(params))
    return {
        "data_source": "official_oee",
        "oee_available": True,
        ("groups" if group_by else "aggregate"): rows_to_dicts(columns, rows),
        "tables_queried": ["tOeeInterval", "tSystem"],
    }


async def _get_proxy_oee(system_id, start_date, end_date, granularity, breakdown) -> Dict[str, Any]:
    group_by = ""
    select_extra = ""
    order_extra = "line"

    if granularity == "daily":
        select_extra = ", CAST(jsa.StartDateTime AS DATE) AS production_date"
        group_by = "GROUP BY CAST(jsa.StartDateTime AS DATE)"
        order_extra = "production_date"
    elif granularity == "weekly":
        select_extra = ", DATEPART(week, jsa.StartDateTime) AS production_week"
        group_by = "GROUP BY DATEPART(week, jsa.StartDateTime)"
        order_extra = "production_week"
    elif granularity == "shift":
        select_extra = ", sh.Name AS shift_name"
        group_by = "GROUP BY sh.Name"
        order_extra = "shift_name"

    where_parts = ["jsa.StartDateTime >= ?", "jsa.StartDateTime < ?"]
    params = [start_date, end_date]
    if system_id:
        where_parts.append("jsa.SystemID = ?")
        params.append(system_id)

    # Availability Proxy
    sql_avail = f"""
        SELECT 
            {(select_extra[1:] if select_extra else "''")} as grp,
            SUM(DATEDIFF(SECOND, jsa.StartDateTime, jsa.EndDateTime)) / 60.0 AS total_active_min,
            DATEDIFF(SECOND, MIN(jsa.StartDateTime), MAX(jsa.EndDateTime)) / 60.0 AS total_elapsed_min
        FROM tJobSystemActual jsa
        LEFT JOIN tShiftHistory sh ON jsa.ShiftHistoryID = sh.ID
        WHERE {' AND '.join(where_parts)}
        {group_by}
    """
    cols_avail, rows_avail = await execute_query(sql_avail, tuple(params))
    avail_data = rows_to_dicts(cols_avail, rows_avail)

    proxy_groups = []
    for entry in avail_data:
        active = entry.get('total_active_min', 0)
        elapsed = entry.get('total_elapsed_min', 0)
        avail_pct = (active / elapsed * 100) if elapsed > 0 else None

        proxy_groups.append({
            granularity: entry.get('grp', 'aggregate'),
            "availability_pct": avail_pct,
            "estimated_oee": avail_pct,  # Simplified proxy
            "performance_pct": None,
        })

    return {
        "line": system_id or "All",
        "date_range": {"start": start_date, "end": end_date},
        "data_source": "proxy",
        "oee_available": False,
        "oee_message": "Official OEE data not yet available. Showing proxy from tJobSystemActual.",
        ("groups" if group_by else "aggregate"): proxy_groups,
        "jobs_analyzed": await _count_jobs(system_id, start_date, end_date),
        "tables_queried": ["tJobSystemActual"],
    }

async def _count_jobs(system_id, start_date, end_date) -> int:
    sql = "SELECT COUNT(DISTINCT JobID) FROM tJobSystemActual jsa WHERE StartDateTime >= ? AND StartDateTime < ?"
    params = [start_date, end_date]
    if system_id:
        sql += " AND SystemID = ?"
        params.append(system_id)
    _, rows = await execute_query(sql, tuple(params))
    return rows[0][0] or 0