"""
Material data queries with intelligent time handling + explainability.

Now returns tables_used + logic so the LLM can always tell the user exactly where the data came from.
"""

import logging
from typing import Any

from src.traksys_mcp.core.database import execute_query
from src.traksys_mcp.core.utils import rows_to_dicts
from src.traksys_mcp.services.time_resolution import TimeResolutionService

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. get_materials (master data - already working)
# ─────────────────────────────────────────────────────────────────────────────
async def get_materials(
        material_id: int | None = None,
        material_name: str | None = None,
        material_code: str | None = None,
        material_type_id: int | None = None,
        material_group_id: int | None = None,
        time_window: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 50,
        time_service: TimeResolutionService | None = None,
) -> dict:
    """Query materials (master data)."""

    # Resolve name/code → ID
    if (material_name or material_code) and material_id is None:
        sql_lookup = """
                     SELECT TOP 1 ID FROM tMaterial
                     WHERE Name = ? OR AltName = ? OR MaterialCode = ?
                     ORDER BY ID DESC
                     """
        params = (material_name or material_code, material_name or material_code, material_code or material_name)
        _, rows = await execute_query(sql_lookup, params)
        if rows and rows[0][0]:
            material_id = rows[0][0]
        else:
            return {"materials": [], "count": 0, "message": f"No material found with name/code '{material_name or material_code}'"}

    safe_limit = max(1, min(int(limit), 1000))

    time_info = None
    actual_start = start_date
    actual_end = end_date

    apply_time_filter = bool(time_window or start_date or end_date)
    if apply_time_filter and time_service:
        resolution = await time_service.resolve(time_window, table="tMaterial")
        time_info = resolution
        actual_start = resolution["actual"]["start"]
        actual_end = resolution["actual"]["end"]

    where_parts: list[str] = []
    params: list[Any] = []

    if material_id is not None:
        where_parts.append("m.ID = ?")
        params.append(material_id)
    if material_type_id is not None:
        where_parts.append("m.MaterialTypeID = ?")
        params.append(material_type_id)
    if material_group_id is not None:
        where_parts.append("m.MaterialGroupID = ?")
        params.append(material_group_id)
    if apply_time_filter:
        if actual_start: where_parts.append("m.ModifiedDateTime >= ?"); params.append(actual_start)
        if actual_end:   where_parts.append("m.ModifiedDateTime <= ?"); params.append(actual_end)

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"
    order_by = "m.ModifiedDateTime DESC" if apply_time_filter else "m.ID ASC"

    sql = f"""
        SELECT TOP {safe_limit}
            m.ID                            AS material_id,
            m.Name                          AS name,
            m.MaterialCode                  AS material_code,
            m.MaterialGroupID               AS material_group_id,
            g.Name                          AS material_group_name,
            m.Units                         AS units,
            m.PlannedSize                   AS planned_size,
            m.ModifiedDateTime              AS modified_datetime,
            m.VersionState                  AS version_state
        FROM tMaterial m
        LEFT JOIN tMaterialGroup g ON m.MaterialGroupID = g.ID
        WHERE {where_clause}
        ORDER BY {order_by}
    """

    columns, rows = await execute_query(sql, tuple(params))
    materials = rows_to_dicts(columns, rows)

    return {
        "materials": materials,
        "count": len(materials),
        "tables_used": ["tMaterial", "tMaterialGroup"],
        "logic": "Direct SELECT from the master material table (tMaterial) with optional LEFT JOIN to group name. "
                 "No time filter unless user explicitly asks for modified date range.",
        "time_info": time_info
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. get_products_using_materials (NEW - real usage)
# ─────────────────────────────────────────────────────────────────────────────
async def get_products_using_materials(
        material_id: int | None = None,
        material_name: str | None = None,
        material_code: str | None = None,
        time_window: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
        time_service: TimeResolutionService | None = None,
) -> dict:
    """Show which products actually used each material in executed batches."""

    # Resolve name/code → ID
    if (material_name or material_code) and material_id is None:
        sql_lookup = """
                     SELECT TOP 1 ID FROM tMaterial
                     WHERE Name = ? OR AltName = ? OR MaterialCode = ?
                     ORDER BY ID DESC
                     """
        params = (material_name or material_code, material_name or material_code, material_code or material_name)
        _, rows = await execute_query(sql_lookup, params)
        if rows and rows[0][0]:
            material_id = rows[0][0]
        else:
            return {"products": [], "count": 0, "message": f"No material found with name/code '{material_name or material_code}'"}

    safe_limit = max(1, min(int(limit), 1000))

    time_info = None
    actual_start = start_date
    actual_end = end_date

    apply_time_filter = bool(time_window or start_date or end_date)
    if apply_time_filter and time_service:
        resolution = await time_service.resolve(time_window, table="tMaterialUseActual")
        time_info = resolution
        actual_start = resolution["actual"]["start"]
        actual_end = resolution["actual"]["end"]

    where_parts: list[str] = []
    params: list[Any] = []

    if material_id is not None:
        where_parts.append("m.ID = ?")
        params.append(material_id)
    if apply_time_filter:
        if actual_start: where_parts.append("mua.DateTime >= ?"); params.append(actual_start)
        if actual_end:   where_parts.append("mua.DateTime <= ?"); params.append(actual_end)

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"

    sql = f"""
        SELECT TOP {safe_limit}
            m.ID                            AS material_id,
            m.Name                          AS material_name,
            m.MaterialCode                  AS material_code,
            p.ID                            AS product_id,
            p.Name                          AS product_name,
            p.ProductCode                   AS product_code,
            SUM(mua.Quantity)               AS total_quantity_used,
            COUNT(DISTINCT j.ID)            AS number_of_batches,
            MAX(mua.DateTime)               AS last_used
        FROM tMaterialUseActual mua
        INNER JOIN tMaterial m ON mua.MaterialID = m.ID
        INNER JOIN tJob j      ON mua.JobID = j.ID
        INNER JOIN tProduct p  ON j.ProductID = p.ID
        WHERE {where_clause}
        GROUP BY m.ID, m.Name, m.MaterialCode, p.ID, p.Name, p.ProductCode
        ORDER BY total_quantity_used DESC, m.Name
    """

    columns, rows = await execute_query(sql, tuple(params))
    usage = rows_to_dicts(columns, rows)

    return {
        "products": usage,
        "count": len(usage),
        "tables_used": ["tMaterial", "tMaterialUseActual", "tJob", "tProduct"],
        "logic": "Joined actual consumption (tMaterialUseActual) → Job (tJob) → Product (tProduct). "
                 "Only real executed batches are considered. There is NO static BOM table in the system.",
        "time_info": time_info
    }