"""
Batch data queries with intelligent time handling.

Uses correct column names from actual EBR_Template schema.
"""

import logging
from typing import Any

from src.traksys_mcp.core.database import execute_query
from src.traksys_mcp.core.utils import rows_to_dicts
from src.traksys_mcp.services.time_resolution import TimeResolutionService

logger = logging.getLogger(__name__)


async def get_batches(
        batch_id: int | None = None,
        batch_name : str | None = None,
        system_id: int | None = None,
        job_id: int | None = None,
        time_window: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        state: int | None = None,
        limit: int = 50,
        time_service: TimeResolutionService | None = None,
) -> dict:
    """
    Query batches with intelligent time handling.

    Joins: tBatch → tJob → tJobBatch → tProduct → tSystem → tShiftHistory

    Returns:
        {
            "batches":   [...],
            "count":     int,
            "time_info": {...} or None
        }
    """

    if batch_name and batch_id is None:
        sql_lookup = """
                     SELECT TOP 1 ID
                     FROM tBatch
                     WHERE Name = ? 
                        OR AltName = ? 
                        OR Lot = ?
                     ORDER BY StartDateTime DESC 
                     """
        _, rows = await execute_query(sql_lookup, (batch_name, batch_name, batch_name))
        if rows and rows[0][0]:
            batch_id = rows[0][0]
            logger.info("Resolved batch_name '%s' → ID %s", batch_name, batch_id)
        else:
            return {
                "batches": [],
                "count": 0,
                "message": f"No batch found with name/code '{batch_name}'",
            }

    safe_limit = max(1, min(int(limit), 1000))

    time_info = None
    actual_start = start_date
    actual_end = end_date

    if time_window and time_service:
        resolution = await time_service.resolve(time_window, table="tBatch")
        time_info = resolution
        actual_start = resolution["actual"]["start"]
        actual_end = resolution["actual"]["end"]

    where_parts: list[str] = []
    params: list[Any] = []

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

    sql = f"""
        SELECT TOP {safe_limit}
            b.ID                                AS batch_id,
            b.Name                              AS batch_name,
            b.AltName                           AS batch_alt_name,
            b.SystemID                          AS system_id,
            b.JobID                             AS job_id,
            b.Lot                               AS lot,
            b.SubLot                            AS sub_lot,
            b.State                             AS state,
            b.StateRequested                    AS state_requested,
            b.StartDateTime                     AS start_datetime,
            b.EndDateTime                       AS end_datetime,
            b.Date                              AS batch_date,
            b.PlannedBatchSize                  AS planned_batch_size,
            b.ActualBatchSize                   AS actual_batch_size,
            b.PlannedBatchDurationSeconds       AS planned_duration_seconds,
            b.[User]                            AS operator,
            j.Name                              AS job_name,
            j.ExternalID                        AS job_external_id,
            j.Lot                               AS job_lot,
            j.PlannedStartDateTime              AS job_planned_start,
            jb.RecipeID                         AS recipe_id,
            jb.PlannedNumberOfBatches           AS planned_number_of_batches,
            jb.PlannedBatchSize                 AS job_planned_batch_size,
            jb.PlannedBatchSizeUnits            AS planned_batch_size_units,
            p.Name                              AS product_name,
            p.ProductCode                       AS product_code,
            p.Description                       AS product_description,
            s.Name                              AS system_name,
            s.ExternalID                        AS system_external_id,
            sh.ID                               AS shift_history_id,
            sh.ShiftID                          AS shift_id,
            sh.TeamID                           AS team_id,
            sh.StartDateTime                    AS shift_start,
            sh.EndDateTime                      AS shift_end,
            sh.Date                             AS shift_date
        FROM tBatch b
        LEFT JOIN tJob          j   ON b.JobID          = j.ID
        LEFT JOIN tJobBatch     jb  ON b.JobID          = jb.JobID
        LEFT JOIN tProduct      p   ON j.ProductID      = p.ID
        LEFT JOIN tSystem       s   ON b.SystemID       = s.ID
        LEFT JOIN tShiftHistory sh  ON b.ShiftHistoryID = sh.ID
        WHERE {where_clause}
        ORDER BY b.StartDateTime DESC
    """

    columns, rows = await execute_query(sql, tuple(params))
    batch_list = rows_to_dicts(columns, rows)

    logger.info(
        "get_batches → %d rows (batch_id=%s, system_id=%s, time=%s)",
        len(batch_list), batch_id, system_id, time_window,
    )

    result: dict[str, Any] = {
        "batches": batch_list,
        "count": len(batch_list),
    }

    if time_info:
        result["time_info"] = time_info

    return result


async def get_batch_parameters(
        batch_id: int | None = None,
        batch_name: str | None = None,
        parameter_names: list[str] | None = None,
        deviation_only: bool = False,
        time_window: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
        time_service: TimeResolutionService | None = None,
) -> dict:
    """
    Retrieve batch process parameters with intelligent time handling.

    Supports lookup by numeric batch_id OR batch_name (name/lot/altname).
    """
    safe_limit = max(1, min(int(limit), 1000))

    # Resolve batch_name to numeric ID if provided
    if batch_name and batch_id is None:
        sql_lookup = """
            SELECT TOP 1 ID
            FROM tBatch
            WHERE Name = ? OR AltName = ? OR Lot = ?
            ORDER BY StartDateTime DESC
        """
        _, rows = await execute_query(sql_lookup, (batch_name, batch_name, batch_name))
        if rows and rows[0][0]:
            batch_id = rows[0][0]
            logger.info("Resolved batch_name '%s' → ID %s", batch_name, batch_id)
        else:
            return {
                "parameters": [],
                "count": 0,
                "message": f"No batch found with name/code '{batch_name}'",
            }

    time_info = None
    actual_start = start_date
    actual_end = end_date

    if time_window and time_service and batch_id is None:
        resolution = await time_service.resolve(time_window, table="tBatch")
        time_info = resolution
        actual_start = resolution["actual"]["start"]
        actual_end = resolution["actual"]["end"]

    where_parts: list[str] = []
    params: list[Any] = []

    if batch_id is not None:
        where_parts.append("bp.BatchID = ?")
        params.append(batch_id)
    else:
        if actual_start:
            where_parts.append("b.StartDateTime >= ?")
            params.append(actual_start)
        if actual_end:
            where_parts.append("b.EndDateTime <= ?")
            params.append(actual_end)

    if parameter_names:
        ph = ", ".join("?" for _ in parameter_names)
        where_parts.append(f"pd.Name IN ({ph})")
        params.extend(parameter_names)

    if deviation_only:
        where_parts.append("""
            TRY_CAST(bp.Value AS float) IS NOT NULL
            AND (
                TRY_CAST(bp.Value AS float) < pd.MinimumValue
                OR TRY_CAST(bp.Value AS float) > pd.MaximumValue
            )
        """)

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"

    sql = f"""
        SELECT TOP {safe_limit}
            bp.ID                       AS parameter_id,
            bp.BatchID                  AS batch_id,
            b.Name                      AS batch_name,
            b.Lot                       AS batch_lot,
            b.SubLot                    AS batch_sublot,
            pd.Name                     AS parameter_name,
            pd.Description              AS parameter_description,
            bp.Value                    AS value_raw,
            TRY_CAST(bp.Value AS float) AS value_numeric,
            pd.MinimumValue             AS min_allowed,
            pd.MaximumValue             AS max_allowed,
            CASE
                WHEN TRY_CAST(bp.Value AS float) IS NOT NULL
                 AND (TRY_CAST(bp.Value AS float) < pd.MinimumValue
                      OR TRY_CAST(bp.Value AS float) > pd.MaximumValue)
                THEN 1 ELSE 0
            END                         AS is_deviation
        FROM tBatchParameter bp
        INNER JOIN tBatch b
            ON bp.BatchID = b.ID
        INNER JOIN tParameterDefinition pd
            ON bp.ParameterDefinitionID = pd.ID
        WHERE {where_clause}
        ORDER BY b.StartDateTime DESC, pd.DisplayOrder, bp.ModifiedDateTime DESC
    """

    columns, rows = await execute_query(sql, tuple(params))
    parameters = rows_to_dicts(columns, rows)

    logger.info(
        "get_batch_parameters → %d rows (batch_id=%s, batch_name=%s, deviation_only=%s)",
        len(parameters), batch_id, batch_name, deviation_only,
    )

    result: dict[str, Any] = {
        "parameters": parameters,
        "count": len(parameters),
    }

    if time_info:
        result["time_info"] = time_info

    return result


async def get_batch_materials(
        batch_id: int | None = None,
        batch_name: str | None = None,
        job_id: int | None = None,
        material_names: list[str] | None = None,
        material_codes: list[str] | None = None,
        time_window: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
        time_service: TimeResolutionService | None = None,
) -> dict:
    """
    Retrieve actual material usage/consumption per batch.

    Supports lookup by batch_id, batch_name (resolves to job_id), or direct job_id.
    """
    safe_limit = max(1, min(int(limit), 1000))

    # Step 1: Resolve batch_name to batch_id
    if batch_name and batch_id is None:
        sql_lookup = """
            SELECT TOP 1 ID
            FROM tBatch
            WHERE Name = ? OR AltName = ? OR Lot = ?
            ORDER BY StartDateTime DESC
        """
        _, rows = await execute_query(sql_lookup, (batch_name, batch_name, batch_name))
        if rows and rows[0][0]:
            batch_id = rows[0][0]
            logger.info("Resolved batch_name '%s' → batch_id %s", batch_name, batch_id)
        else:
            return {
                "materials": [],
                "count": 0,
                "message": f"No batch found with name/code '{batch_name}'",
            }

    # Step 2: Resolve batch_id to job_id
    if batch_id is not None and job_id is None:
        sql_job = "SELECT TOP 1 JobID FROM tBatch WHERE ID = ?"
        _, rows = await execute_query(sql_job, (batch_id,))
        if rows and rows[0][0]:
            job_id = rows[0][0]
            logger.info("Resolved batch_id %s → job_id %s", batch_id, job_id)
        else:
            return {
                "materials": [],
                "count": 0,
                "message": f"No job found for batch_id {batch_id}",
            }

    # Step 3: Must have job_id to query materials
    if job_id is None:
        return {
            "materials": [],
            "count": 0,
            "message": "Must provide batch_id, batch_name, or job_id",
        }

    time_info = None
    actual_start = start_date
    actual_end = end_date

    if time_window and time_service:
        resolution = await time_service.resolve(time_window, table="tMaterialUseActual")
        time_info = resolution
        actual_start = resolution["actual"]["start"]
        actual_end = resolution["actual"]["end"]

    where_parts: list[str] = []
    params: list[Any] = []

    where_parts.append("mua.JobID = ?")
    params.append(job_id)

    if actual_start:
        where_parts.append("mua.DateTime >= ?")
        params.append(actual_start)

    if actual_end:
        where_parts.append("mua.DateTime <= ?")
        params.append(actual_end)

    if material_names:
        ph = ", ".join("?" for _ in material_names)
        where_parts.append(f"mat.Name IN ({ph})")
        params.extend(material_names)

    if material_codes:
        ph = ", ".join("?" for _ in material_codes)
        where_parts.append(f"mat.MaterialCode IN ({ph})")
        params.extend(material_codes)

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"

    sql = f"""
        SELECT TOP {safe_limit}
            mua.ID                      AS material_use_id,
            mua.JobID                   AS job_id,
            b.ID                        AS batch_id,
            b.Name                      AS batch_name,
            b.Lot                       AS batch_lot,
            b.SubLot                    AS batch_sublot,
            mat.Name                    AS material_name,
            mat.MaterialCode            AS material_code,
            mat.Units                   AS units,
            mua.Quantity                AS consumed_quantity
        FROM tMaterialUseActual mua
        INNER JOIN tBatch b
            ON mua.JobID = b.JobID
        INNER JOIN tMaterial mat
            ON mua.MaterialID = mat.ID
        WHERE {where_clause}
        ORDER BY mua.DateTime DESC
    """

    columns, rows = await execute_query(sql, tuple(params))
    materials = rows_to_dicts(columns, rows)

    logger.info(
        "get_batch_materials → %d rows (batch_id=%s, batch_name=%s, job_id=%s)",
        len(materials), batch_id, batch_name, job_id,
    )

    result: dict[str, Any] = {
        "materials": materials,
        "count": len(materials),
    }

    if time_info:
        result["time_info"] = time_info

    return result

async def get_batch_quality(
        batch_id: int | None = None,
        product_name: str | None = None,
        system_id: int | None = None,
        time_window: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        category_filter: list[str] | None = None,
        limit: int = 50,
        time_service: TimeResolutionService | None = None,
) -> dict:
    """
    Query quality loss events with intelligent time handling.

    Answers:
        Q7 — Which batches in the last N days had quality deviations?
        Q8 — Most common root causes of quality rejects for a product?

    Joins:
        tBatchQualityLoss
            → tBatch → tJob → tProduct → tSystem
            → tBatchQualityLossCategory → tBatchQualityLossCategoryGroup

    Returns:
        {
            "quality_events": [...],
            "count":          int,
            "time_info":      {...} or None
        }
    """
    safe_limit = max(1, min(int(limit), 500))

    time_info = None
    actual_start = start_date
    actual_end = end_date

    if time_window and time_service and batch_id is None:
        resolution = await time_service.resolve(time_window, table="tBatch")
        time_info = resolution
        actual_start = resolution["actual"]["start"]
        actual_end = resolution["actual"]["end"]

    where_parts: list[str] = []
    params: list[Any] = []

    if batch_id is not None:
        where_parts.append("bql.BatchID = ?")
        params.append(batch_id)
    else:
        if actual_start:
            where_parts.append("b.StartDateTime >= ?")
            params.append(actual_start)
        if actual_end:
            where_parts.append("b.EndDateTime <= ?")
            params.append(actual_end)

    if product_name:
        where_parts.append("p.Name = ?")
        params.append(product_name)

    if system_id is not None:
        where_parts.append("b.SystemID = ?")
        params.append(system_id)

    if category_filter:
        ph = ", ".join("?" for _ in category_filter)
        where_parts.append(f"bqlc.Name IN ({ph})")
        params.extend(category_filter)

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"

    sql = f"""
        SELECT TOP {safe_limit}
            bql.ID                      AS quality_loss_id,
            bql.BatchID                 AS batch_id,
            bql.Quantity                AS loss_quantity,
            bql.ModifiedDateTime        AS recorded_at,

            -- Category (LEFT JOIN keeps uncategorised losses)
            bqlc.Name                   AS category_name,
            bqlc.Description            AS category_description,
            bqlcg.Name                  AS category_group_name,

            -- Batch context
            b.Name                      AS batch_name,
            b.Lot                       AS batch_lot,
            b.SubLot                    AS batch_sublot,
            b.StartDateTime             AS batch_start,
            b.EndDateTime               AS batch_end,
            b.ActualBatchSize           AS actual_batch_size,
            b.PlannedBatchSize          AS planned_batch_size,
            CASE
                WHEN b.ActualBatchSize > 0
                THEN ROUND((bql.Quantity / b.ActualBatchSize) * 100, 2)
                ELSE NULL
            END                         AS loss_percentage,

            -- Product and line
            p.Name                      AS product_name,
            p.ProductCode               AS product_code,
            s.Name                      AS system_name,
            s.ExternalID                AS system_external_id

        FROM tBatchQualityLoss bql
        INNER JOIN tBatch b
            ON bql.BatchID = b.ID
        LEFT JOIN tBatchQualityLossCategory bqlc
            ON bql.BatchQualityLossCategoryID = bqlc.ID
        LEFT JOIN tBatchQualityLossCategoryGroup bqlcg
            ON bqlc.BatchQualityLossCategoryGroupID = bqlcg.ID
        LEFT JOIN tJob j
            ON b.JobID = j.ID
        LEFT JOIN tProduct p
            ON j.ProductID = p.ID
        LEFT JOIN tSystem s
            ON b.SystemID = s.ID
        WHERE {where_clause}
        ORDER BY bql.ModifiedDateTime DESC
    """

    columns, rows = await execute_query(sql, tuple(params))
    quality_events = rows_to_dicts(columns, rows)

    logger.info(
        "get_batch_quality → %d events (batch_id=%s, time=%s, categories=%s)",
        len(quality_events), batch_id, time_window, category_filter,
    )

    result: dict[str, Any] = {
        "quality_events": quality_events,
        "count": len(quality_events),
    }

    if time_info:
        result["time_info"] = time_info

    return result