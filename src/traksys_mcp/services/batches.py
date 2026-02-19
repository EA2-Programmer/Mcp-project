"""
Batch data queries with intelligent time handling.

Uses correct column names from actual EBR_Template schema.
"""

from src.traksys_mcp.core.database import execute_query
from src.traksys_mcp.core.utils import rows_to_dicts
from src.traksys_mcp.services.time_resolution import TimeResolutionService
from typing import Optional, List, Any
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


async def get_batch_parameters(
        batch_id: Optional[int] = None,
        parameter_names: Optional[list[str]] = None,
        deviation_only: bool = False,
        time_window: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        time_service: Optional[TimeResolutionService] = None
) -> dict:
    """
    Retrieve batch process parameters with intelligent time handling.

    Main tables: tBatchParameter, tBatch, tParameterDefinition

    Supports:
    - specific batch → ignores time filters
    - time-based query → uses tBatch.StartDateTime / EndDateTime
    - deviation filtering (simple min/max check)
    - parameter name filtering

    Returns:
        {
            "parameters": list of dicts,
            "count": int,
            "time_info": dict or None
        }
    """
    time_info = None
    actual_start = start_date
    actual_end = end_date

    # Resolve natural language time → fallback-aware dates
    if time_window and time_service and batch_id is None:
        resolution = await time_service.resolve(time_window, table="tBatch")
        time_info = resolution
        actual_start = resolution["actual"]["start"].split("T")[0]
        actual_end   = resolution["actual"]["end"].split("T")[0]

    where_parts = []
    params = []

    if batch_id is not None:
        where_parts.append("bp.BatchID = ?")
        params.append(batch_id)
    elif actual_start:
        where_parts.append("b.StartDateTime >= ?")
        params.append(actual_start + " 00:00:00")
    if actual_end:
        where_parts.append("b.EndDateTime <= ?")
        params.append(actual_end + " 23:59:59")

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

    # Main query – uses correct column names from EBR_Template schema
    sql = f"""
        SELECT TOP {limit}
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
            bp.ModifiedDateTime         AS recorded_at,
            b.StartDateTime             AS batch_start,
            b.EndDateTime               AS batch_end,
            CASE WHEN TRY_CAST(bp.Value AS float) IS NOT NULL
                 AND (TRY_CAST(bp.Value AS float) < pd.MinimumValue
                      OR TRY_CAST(bp.Value AS float) > pd.MaximumValue)
                 THEN 1 ELSE 0 END      AS is_deviation
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

    result = {
        "parameters": parameters,
        "count": len(parameters)
    }

    if time_info:
        result["time_info"] = time_info

    logger.info(f"get_batch_parameters → {len(parameters)} rows "
                f"(batch_id={batch_id}, deviation_only={deviation_only}, time={time_window})")

    return result


async def get_batch_materials(
        batch_id: Optional[int] = None,
        material_names: Optional[List[str]] = None,
        material_codes: Optional[List[str]] = None,
        time_window: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        time_service: Optional[TimeResolutionService] = None
) -> dict:
    """
    Retrieve actual material usage/consumption per batch.

    Main tables: tMaterialUseActual, tBatch, tMaterial

    Supports:
    - specific batch → ignores time filters
    - time-based query → uses tBatch.StartDateTime
    - filter by material name or code
    - intelligent time fallback via DataAvailabilityCache

    Returns:
        {
            "materials": list of dicts,
            "count": int,
            "time_info": dict or None
        }
    """
    time_info = None
    actual_start = start_date
    actual_end = end_date

    # Resolve natural language time → fallback-aware dates
    if time_window and time_service and batch_id is None:
        resolution = await time_service.resolve(time_window, table="tBatch")
        time_info = resolution
        actual_start = resolution["actual"]["start"].split("T")[0]
        actual_end   = resolution["actual"]["end"].split("T")[0]

    where_parts = []
    params: List[Any] = []

    if batch_id is not None:
        where_parts.append("mua.BatchID = ?")
        params.append(batch_id)
    elif actual_start:
        where_parts.append("b.StartDateTime >= ?")
        params.append(actual_start + " 00:00:00")
    if actual_end:
        where_parts.append("b.EndDateTime <= ?")
        params.append(actual_end + " 23:59:59")

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
        SELECT TOP {limit}
            mua.ID                      AS material_use_id,
            mua.BatchID                 AS batch_id,
            b.Name                      AS batch_name,
            b.Lot                       AS batch_lot,
            b.SubLot                    AS batch_sublot,
            mat.Name                    AS material_name,
            mat.MaterialCode            AS material_code,
            mat.Units                   AS units,
            mua.Quantity                AS consumed_quantity,
            mua.PlannedQuantity         AS planned_quantity,          -- may be NULL
            mua.DateTime                AS consumption_datetime,
            b.StartDateTime             AS batch_start,
            b.EndDateTime               AS batch_end,
            CASE 
                WHEN mua.PlannedQuantity IS NOT NULL 
                     AND mua.Quantity > mua.PlannedQuantity * 1.1    -- example 10% over
                THEN 1 ELSE 0 
            END                         AS is_over_consumption
        FROM tMaterialUseActual mua
        INNER JOIN tBatch b
            ON mua.BatchID = b.ID
        INNER JOIN tMaterial mat
            ON mua.MaterialID = mat.ID
        WHERE {where_clause}
        ORDER BY b.StartDateTime DESC, mua.DateTime DESC
    """

    columns, rows = await execute_query(sql, tuple(params))
    materials = rows_to_dicts(columns, rows)

    result = {
        "materials": materials,
        "count": len(materials)
    }

    if time_info:
        result["time_info"] = time_info

    logger.info(f"get_batch_materials → {len(materials)} rows "
                f"(batch_id={batch_id}, time={time_window})")

    return result