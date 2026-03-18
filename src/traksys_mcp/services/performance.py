import logging
from typing import Optional, Any

from src.traksys_mcp.core.database import execute_query
from src.traksys_mcp.core.utils import rows_to_dicts

logger = logging.getLogger(__name__)


async def get_equipment_state(
        system_id: Optional[int] = None,
        system_name: Optional[str] = None,
        area_id: Optional[int] = None,
        include_active_faults: bool = False,
        limit: int = 50,
        trace_span=None,
) -> dict:
    """Retrieve LIVE equipment status, active production context, and active faults without using tags."""

    # 1. Resolve System Name to ID if needed
    if system_name and system_id is None:
        sql_lookup = "SELECT TOP 1 ID FROM tSystem WHERE Name LIKE ? OR AltName LIKE ?"
        _, rows = await execute_query(
            sql_lookup,
            (f"%{system_name}%", f"%{system_name}%"),
            trace_span=trace_span,
            span_name="system_name_lookup",
        )
        if rows:
            system_id = rows[0][0]
        else:
            return {"equipment": [], "message": f"No equipment found with name '{system_name}'"}

    safe_limit = max(1, min(int(limit), 100))
    where_parts = ["s.Enabled = 1", "s.IsTemplate = 0"]
    params = []

    if system_id:
        where_parts.append("s.ID = ?")
        params.append(system_id)
    if area_id:
        where_parts.append("s.AreaID = ?")
        params.append(area_id)

    where_clause = " AND ".join(where_parts)

    # 2. Base Equipment Query (Relational Context via tJobSystemActual)
    sql_base = f"""
        SELECT TOP {safe_limit}
            s.ID AS system_id,
            s.Name AS system_name,
            s.Description,
            s.AreaID AS area_id,
            s.IsManual AS is_manual,
            s.Enabled AS is_enabled,
            -- Context derived relationally, not from tags
            j.Name AS active_job_name,
            p.Name AS active_product_name,
            p.ProductCode AS active_product_code,
            CONVERT(varchar(50), jsa.StartDateTime, 127) AS job_start_time
        FROM tSystem s
        LEFT JOIN tJobSystemActual jsa ON s.ID = jsa.SystemID AND jsa.EndDateTime IS NULL
        LEFT JOIN tJob j ON jsa.JobID = j.ID
        LEFT JOIN tProduct p ON j.ProductID = p.ID
        WHERE {where_clause}
    """

    columns, rows = await execute_query(
        sql_base, tuple(params), trace_span=trace_span, span_name="live_equipment_base"
    )
    equipment_data = rows_to_dicts(columns, rows)

    # 3. Enhance with Active Faults (Unclosed Events)
    for equip in equipment_data:
        sid = equip["system_id"]

        if include_active_faults:
            sql_faults = """
                         SELECT e.ID                                                   AS event_id, \
                                CONVERT(varchar(50), e.StartDateTime, 127) AS fault_start_time, \
                                DATEDIFF(minute, e.StartDateTime, SYSDATETIMEOFFSET()) AS minutes_down, \
                                ed.Name                                                AS fault_name, \
                                ed.Description                                         AS fault_description, \
                                e.Notes                                                AS operator_notes
                         FROM tEvent e
                                  INNER JOIN tEventDefinition ed ON e.EventDefinitionID = ed.ID
                         WHERE e.EndDateTime IS NULL
                           AND ed.SystemID = ?
                         ORDER BY e.StartDateTime DESC \
                         """
            fault_cols, fault_rows = await execute_query(
                sql_faults, (sid,), trace_span=trace_span, span_name=f"active_faults_{sid}"
            )
            equip["active_faults"] = rows_to_dicts(fault_cols, fault_rows)
            equip["is_currently_faulted"] = len(equip["active_faults"]) > 0

    return {
        "equipment": equipment_data,
        "count": len(equipment_data),
        "methodology": {
            "approach": "Real-time relational query of equipment status and unclosed faults.",
            "signals_checked": [
                "Checked tSystem for machine availability.",
                "Checked tJobSystemActual (EndDateTime IS NULL) to find actively running jobs.",
                "Checked tEvent for records with NULL EndDateTime to find active stoppages." if include_active_faults else "Active faults skipped."
            ]
        }
    }