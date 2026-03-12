"""
OEE calculation service using client-confirmed tables.

Fixed: [Key] brackets because 'Key' is a SQL reserved word.
"""

import logging
from typing import Any

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
) -> dict:
    """
    Calculate OEE using tOeeCalculation + tOeeInterval.
    """
    if not start_date or not end_date:
        return {"oee": [], "count": 0, "message": "start_date and end_date are required"}

    # Step 1: Resolve line name → OeeCalculationID
    sql_lookup = """
        SELECT TOP 1 ID
        FROM tOeeCalculation
        WHERE Name LIKE ? 
           OR [Key] LIKE ?          -- FIXED: brackets because 'Key' is reserved
           OR CAST(SystemID AS varchar) = ?
        ORDER BY ID
    """
    _, rows = await execute_query(sql_lookup, (f"%{line}%", f"%{line}%", line))
    if not rows or not rows[0][0]:
        return {"oee": [], "count": 0, "message": f"No OEE configuration found for line '{line}'"}

    oee_calc_id = rows[0][0]

    # Step 2: Time resolution
    time_info = None
    actual_start = start_date
    actual_end = end_date
    if time_service:
        resolution = await time_service.resolve(f"{start_date} to {end_date}", table="tOeeInterval")
        time_info = resolution
        actual_start = resolution["actual"]["start"]
        actual_end = resolution["actual"]["end"]

    # Step 3: Aggregate intervals
    sql = f"""
        SELECT 
            i.Date AS period,
            SUM(i.TotalCalculationUnitsCount)   AS total_units,
            SUM(i.GoodCalculationUnitsCount)    AS good_units,
            SUM(i.BadCalculationUnitsCount)     AS bad_units,
            SUM(i.AvailabilityLossSeconds)      AS avail_loss_sec,
            SUM(i.PerformanceLossSeconds)       AS perf_loss_sec,
            AVG(i.TheoreticalCalculationUnitsPerMinute) AS theo_rate
        FROM tOeeInterval i
        WHERE i.OeeCalculationID = ?
          AND i.StartDateTime >= ?
          AND i.EndDateTime   <= ?
        GROUP BY i.Date
        ORDER BY i.Date
    """
    params = (oee_calc_id, actual_start, actual_end)
    columns, rows = await execute_query(sql, params)
    intervals = rows_to_dicts(columns, rows)

    # Step 4: Compute OEE
    result = []
    for row in intervals:
        total = row.get("total_units") or 1
        good = row.get("good_units") or 0

        avail = max(0, 1 - (row.get("avail_loss_sec") or 0) / 3600)
        perf = good / (row.get("theo_rate") * total) if row.get("theo_rate") else 0
        qual = good / total

        oee = avail * perf * qual * 100

        item = {
            "period": str(row["period"]),
            "oee": round(oee, 2),
            "total_units": int(total),
            "good_units": int(good),
        }
        if breakdown:
            item.update({
                "availability": round(avail * 100, 2),
                "performance": round(perf * 100, 2),
                "quality": round(qual * 100, 2),
            })
        result.append(item)

    return {
        "oee": result,
        "count": len(result),
        "tables_used": ["tOeeCalculation", "tOeeInterval"],
        "logic": "Resolved line name to OeeCalculationID using [Key] (bracketed because it's a reserved word), "
                 "then aggregated real intervals from tOeeInterval and computed OEE = Availability × Performance × Quality.",
        "time_info": time_info
    }

# ─────────────────────────────────────────────────────────────────────────────
# 2. NEW: get_oee_downtime_events (FIXED VERSION)
# ─────────────────────────────────────────────────────────────────────────────
async def get_oee_downtime_events(
        line: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 50,
        time_service: TimeResolutionService | None = None,
) -> dict:
    """
    Show actual downtime and quality events for a line.
    """
    if not start_date or not end_date:
        return {"events": [], "count": 0, "message": "start_date and end_date required"}

    # Resolve line name to OeeCalculationID
    sql_lookup = """
        SELECT TOP 1 ID FROM tOeeCalculation
        WHERE Name LIKE ? OR [Key] LIKE ? OR CAST(SystemID AS varchar) = ?
    """
    _, rows = await execute_query(sql_lookup, (f"%{line}%", f"%{line}%", line))
    if not rows:
        return {"events": [], "count": 0, "message": f"No line config for '{line}'"}

    oee_calc_id = rows[0][0]

    # Time handling
    time_info = None
    actual_start = start_date
    actual_end = end_date
    if time_service:
        resolution = await time_service.resolve(f"{start_date} to {end_date}", table="tEvent")
        time_info = resolution
        actual_start = resolution["actual"]["start"]
        actual_end = resolution["actual"]["end"]

    safe_limit = max(1, min(int(limit), 500))

    sql = f"""
        SELECT TOP {safe_limit}
            e.ID AS event_id,
            e.StartDateTime,
            e.EndDateTime,
            DATEDIFF(second, e.StartDateTime, e.EndDateTime) AS duration_seconds,
            ed.Name AS event_name,
            ed.Description AS event_description,
            e.Impact AS impact_seconds,
            e.Count AS event_count,
            e.Notes
        FROM tEvent e
        INNER JOIN tEventDefinition ed ON e.EventDefinitionID = ed.ID
        WHERE e.StartDateTime >= ?
          AND e.EndDateTime   <= ?
          AND ed.SystemID = (SELECT SystemID FROM tOeeCalculation WHERE ID = ?)
        ORDER BY e.StartDateTime DESC
    """
    params = (actual_start, actual_end, oee_calc_id)
    columns, rows = await execute_query(sql, params)
    events = rows_to_dicts(columns, rows)

    return {
        "events": events,
        "count": len(events),
        "tables_used": ["tEvent", "tEventDefinition", "tOeeCalculation"],
        "logic": "Joined real events (tEvent) to their definitions (tEventDefinition) "
                 "and filtered by the line's OEE configuration. Shows exact downtime "
                 "that affected Availability and Quality.",
        "time_info": time_info
    }