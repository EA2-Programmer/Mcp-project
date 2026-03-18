"""
OEE and Downtime Event Tracking Service.

Mathematically sound OEE logic utilizing Planned vs Operating Time,
and enhanced downtime queries including fault codes.
"""

import logging

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
    Calculate OEE using tOeeCalculation + tOeeInterval with correct manufacturing math.
    """
    if not start_date or not end_date:
        return {"oee": [], "count": 0, "message": "start_date and end_date are required"}

    # Step 1: Resolve line name → OeeCalculationID
    sql_lookup = """
        SELECT TOP 1 ID
        FROM tOeeCalculation
        WHERE Name LIKE ? 
           OR [Key] LIKE ? 
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

    # Step 3: Aggregate intervals and fetch scheduled time components
    sql = """
        SELECT 
            i.Date AS period,
            SUM(DATEDIFF(second, i.StartDateTime, i.EndDateTime)) AS calendar_sec,
            SUM(i.SystemNotScheduledSeconds)    AS not_scheduled_sec,
            SUM(i.TotalCalculationUnitsCount)   AS total_units,
            SUM(i.GoodCalculationUnitsCount)    AS good_units,
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

    # Step 4: Compute Industry-Standard OEE
    result = []
    for row in intervals:
        # Safely extract values
        calendar_sec = row.get("calendar_sec") or 0
        not_scheduled_sec = row.get("not_scheduled_sec") or 0
        avail_loss_sec = row.get("avail_loss_sec") or 0

        total_units = row.get("total_units") or 0
        good_units = row.get("good_units") or 0
        theo_rate = row.get("theo_rate") or 1.0

        # Core Time Buckets
        planned_production_sec = max(0, calendar_sec - not_scheduled_sec)
        operating_sec = max(0, planned_production_sec - avail_loss_sec)

        # 1. Availability Calculation
        avail = operating_sec / planned_production_sec if planned_production_sec > 0 else 0.0

        # 2. Performance Calculation (Actual Output / Expected Output during operating time)
        expected_units = (operating_sec / 60.0) * theo_rate
        perf = total_units / expected_units if expected_units > 0 else 0.0

        # 3. Quality Calculation
        qual = good_units / total_units if total_units > 0 else 0.0

        # Clamp values to logical maximums (100%) in case of minor data overlaps
        avail = min(1.0, avail)
        perf = min(1.0, perf)
        qual = min(1.0, qual)

        oee = avail * perf * qual * 100

        item = {
            "period": str(row["period"]),
            "oee": round(oee, 2),
            "total_units": int(total_units),
            "good_units": int(good_units),
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
        "logic": "Calculated precise OEE using actual operating time (accounting for SystemNotScheduledSeconds) and true performance ratios (actual vs. theoretical speed).",
        "time_info": time_info
    }


# get_oee_downtime_events
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
            e.Impact AS impact_seconds,
            ed.Name AS event_category,
            ed.Description AS event_description,
            ec.Code AS fault_code,
            ec.Name AS fault_name,
            e.Count AS event_count,
            e.Notes
        FROM tEvent e
        INNER JOIN tEventDefinition ed ON e.EventDefinitionID = ed.ID
        LEFT JOIN tEventCode ec ON e.EventCodeID = ec.ID
        WHERE e.StartDateTime >= ?
          AND e.StartDateTime <= ?
          AND ed.SystemID = (SELECT SystemID FROM tOeeCalculation WHERE ID = ?)
        ORDER BY e.StartDateTime DESC
    """
    params = (actual_start, actual_end, oee_calc_id)
    columns, rows = await execute_query(sql, params)
    events = rows_to_dicts(columns, rows)

    return {
        "events": events,
        "count": len(events),
        "tables_used": ["tEvent", "tEventDefinition", "tEventCode", "tOeeCalculation"],
        "logic": "Joined real events (tEvent) to definitions (tEventDefinition) and fault codes (tEventCode). Filtered by the SystemID tied to the OEE configuration.",
        "time_info": time_info
    }