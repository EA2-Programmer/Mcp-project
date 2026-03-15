import logging
from typing import Any

from src.traksys_mcp.core.database import execute_query
from src.traksys_mcp.core.utils import rows_to_dicts
from src.traksys_mcp.services.time_resolution import TimeResolutionService
from src.traksys_mcp.utils.batch_queries import (
    BATCH_NAME_LOOKUP,
    SYSTEM_NAME_LOOKUP,
    BATCH_JOB_LOOKUP,
    BATCH_INFO,
    BATCH_STEPS,
    OPERATOR_REMARKS_BY_BATCH,
    COMPLIANCE_TASKS_BY_BATCH,
    build_batches_query,
    build_parameters_query,
    build_materials_query,
    build_quality_deviations_query,
    build_quality_remarks_query,
    build_quality_incomplete_tasks_query,
)

logger = logging.getLogger(__name__)


async def _resolve_batch_name(batch_name: str, trace_span=None) -> int | None:
    """Resolve a batch name/lot/altname to a numeric ID."""
    _, rows = await execute_query(
        BATCH_NAME_LOOKUP,
        (batch_name, batch_name, batch_name),
        trace_span=trace_span,
        span_name="batch_name_lookup",
    )
    if rows and rows[0][0]:
        logger.info("Resolved batch_name '%s' → ID %s", batch_name, rows[0][0])
        return rows[0][0]
    return None


async def _resolve_system_name(system_name: str, trace_span=None) -> int | None:
    """Resolve a system name to a numeric ID."""
    _, rows = await execute_query(
        SYSTEM_NAME_LOOKUP,
        (system_name,),
        trace_span=trace_span,
        span_name="system_name_lookup",
    )
    if rows and rows[0][0]:
        logger.info("Resolved system_name '%s' → ID %s", system_name, rows[0][0])
        return rows[0][0]
    return None


async def get_batches(
        batch_id: int | None = None,
        batch_name: str | None = None,
        system_id: int | None = None,
        system_name: str | None = None,
        job_id: int | None = None,
        time_window: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        state: int | None = None,
        limit: int = 50,
        time_service: TimeResolutionService | None = None,
        trace_span=None,
) -> dict:
    """
    Query batches with time handling also.
    Joins: tBatch → tJob → tJobBatch → tProduct → tSystem → tShiftHistory
    """
    if batch_name and batch_id is None:
        batch_id = await _resolve_batch_name(batch_name, trace_span)
        if batch_id is None:
            return {"batches": [], "count": 0, "message": f"No batch found with name/code '{batch_name}'"}

    if system_name and system_id is None:
        system_id = await _resolve_system_name(system_name, trace_span)

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

    columns, rows = await execute_query(
        build_batches_query(safe_limit, where_clause),
        tuple(params),
        trace_span=trace_span,
        span_name="batch_main_query",
    )
    batch_list = rows_to_dicts(columns, rows)

    logger.info(
        "get_batches → %d rows (batch_id=%s, system_id=%s, time=%s)",
        len(batch_list), batch_id, system_id, time_window,
    )

    result: dict[str, Any] = {
        "batches": batch_list,
        "count": len(batch_list),
        "methodology": {
            "approach": "Batch query with time-awareness and  fallback",
            "signals_checked": [
                f"Queried tBatch joined with tJob, tProduct, tSystem, tShiftHistory ({len(batch_list)} batches returned)",
                "Time window resolved via TimeResolutionService — natural language converted to exact dates",
                "Fallback triggered automatically when requested dates have no data — uses nearest available range",
                "Batch name resolved to numeric ID via tBatch.Name / AltName / Lot lookup when provided",
            ],
            "verdict_logic": (
                "No batch_id or batch_name required — omit both to query by time window or line. "
                f"Results ordered by StartDateTime DESC. Limit: {safe_limit}."
            ),
            "data_sources": ["tBatch", "tJob", "tJobBatch", "tProduct", "tSystem", "tShiftHistory"],
            "coverage": (
                f"{len(batch_list)} batches returned"
                + (f" (system_id={system_id})" if system_id else "")
                + (f" from {actual_start} to {actual_end}" if actual_start else "")
            ),
        },
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
        trace_span=None,
) -> dict:
    """Retrieve batch process parameters with optional deviation filtering."""
    safe_limit = max(1, min(int(limit), 1000))

    if batch_name and batch_id is None:
        batch_id = await _resolve_batch_name(batch_name, trace_span)
        if batch_id is None:
            return {"parameters": [], "count": 0, "message": f"No batch found with name/code '{batch_name}'"}

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

    columns, rows = await execute_query(
        build_parameters_query(safe_limit, where_clause),
        tuple(params),
        trace_span=trace_span,
        span_name="batch_parameters_main",
    )
    parameters = rows_to_dicts(columns, rows)

    logger.info(
        "get_batch_parameters → %d rows (batch_id=%s, batch_name=%s, deviation_only=%s)",
        len(parameters), batch_id, batch_name, deviation_only,
    )

    deviation_count = sum(1 for p in parameters if p.get("is_deviation") == 1)

    result: dict[str, Any] = {
        "parameters": parameters,
        "count": len(parameters),
        "methodology": {
            "approach": "Process parameter retrieval with deviation detection",
            "signals_checked": [
                f"Read {len(parameters)} parameter records from tBatchParameter",
                "Each reading compared against allowed min/max from tParameterDefinition",
                (
                    "deviation_only=True: only out-of-spec readings returned"
                    if deviation_only
                    else f"All readings returned — {deviation_count} out-of-spec detected. Set deviation_only=True to filter to failures only"
                ),
            ],
            "verdict_logic": (
                "A parameter is flagged when its value falls outside the min/max bounds in tParameterDefinition. "
                "No batch_id required — use time_window to query across a date range."
            ),
            "data_sources": ["tBatchParameter", "tParameterDefinition", "tBatch"],
            "coverage": (
                f"{len(parameters)} readings checked, {deviation_count} deviations found"
                + (f" for batch_id={batch_id}" if batch_id else "")
                + (f" from {actual_start} to {actual_end}" if actual_start and not batch_id else "")
            ),
        },
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
        trace_span=None,
) -> dict:
    """
    Retrieve actual material usage per batch.
    Supports lookup by batch_id, batch_name (resolves to job_id), or direct job_id.
    """
    safe_limit = max(1, min(int(limit), 1000))

    if batch_name and batch_id is None:
        batch_id = await _resolve_batch_name(batch_name, trace_span)
        if batch_id is None:
            return {"materials": [], "count": 0, "message": f"No batch found with name/code '{batch_name}'"}

    if batch_id is not None and job_id is None:
        _, rows = await execute_query(
            BATCH_JOB_LOOKUP, (batch_id,), trace_span=trace_span, span_name="batch_job_lookup",
        )
        if rows and rows[0][0]:
            job_id = rows[0][0]
            logger.info("Resolved batch_id %s → job_id %s", batch_id, job_id)
        else:
            return {"materials": [], "count": 0, "message": f"No job found for batch_id {batch_id}"}

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

    if job_id is not None:
        # Specific batch/job mode — join via job_id
        where_parts.append("mua.JobID = ?")
        params.append(job_id)
        if actual_start:
            where_parts.append("mua.DateTime >= ?")
            params.append(actual_start)
        if actual_end:
            where_parts.append("mua.DateTime <= ?")
            params.append(actual_end)
    else:
        # Open-ended mode — filter by time range via tBatch join
        if actual_start:
            where_parts.append("b.StartDateTime >= ?")
            params.append(actual_start)
        if actual_end:
            where_parts.append("b.StartDateTime <= ?")
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

    columns, rows = await execute_query(
        build_materials_query(safe_limit, where_clause),
        tuple(params),
        trace_span=trace_span,
        span_name="materials_main_query",
    )
    materials = rows_to_dicts(columns, rows)

    logger.info(
        "get_batch_materials → %d rows (batch_id=%s, batch_name=%s, job_id=%s)",
        len(materials), batch_id, batch_name, job_id,
    )

    unique_materials = list({m.get("material_name", "?") for m in materials})
    total_qty = sum(float(m.get("consumed_quantity") or 0) for m in materials)
    unique_batches = len({m.get("batch_id") for m in materials})

    result: dict[str, Any] = {
        "materials": materials,
        "count": len(materials),
        "methodology": {
            "approach": "Material consumption tracing via tBatch → tJob → tMaterialUseActual",
            "signals_checked": [
                f"Retrieved {len(materials)} material consumption records from tMaterialUseActual",
                f"Covered {unique_batches} batch(es) across {len(unique_materials)} material type(s)",
                "Quantities in KGR (Kilogram Reactive — pharmaceutical unit, not standard KG)",
                "Silo source not available: tLocation is empty (SAP integration not yet active).",
            ],
            "verdict_logic": (
                "No batch_id required — use time_window to query consumption across a date range. "
                "When batch_id is given, resolves to JobID first, then queries tMaterialUseActual."
            ),
            "data_sources": ["tMaterialUseActual", "tMaterial", "tBatch", "tJob"],
            "coverage": (
                f"{len(materials)} records, {len(unique_materials)} material types"
                + (f", total: {round(total_qty, 2)} KGR" if total_qty > 0 else "")
                + (f" across {unique_batches} batch(es)" if unique_batches > 1 else "")
            ),
        },
    }

    if time_info:
        result["time_info"] = time_info

    return result


async def get_batch_details(
        batch_id: int | None = None,
        batch_name: str | None = None,
        time_service: TimeResolutionService | None = None,
        trace_span=None,
) -> dict:
    """
    Retrieve deep detail for a single batch.

    Returns four sections:
        - batch_info:        core batch + job + product + line data
        - steps:             all steps executed (tBatchStep + tFunctionDefinition)
        - operator_remarks:  free-text remarks entered by operators (_DBR)
        - compliance_tasks:  mandatory tasks and completion status (tTask)
    """
    _empty = {"batch_info": None, "steps": [], "operator_remarks": [], "compliance_tasks": []}

    if batch_name and batch_id is None:
        batch_id = await _resolve_batch_name(batch_name, trace_span)
        if batch_id is None:
            return {**_empty, "message": f"No batch found with name/code '{batch_name}'"}

    if batch_id is None:
        return {**_empty, "message": "Must provide batch_id or batch_name"}

    columns, rows = await execute_query(BATCH_INFO, (batch_id,), trace_span=trace_span, span_name="batch_main_info")
    batch_info_list = rows_to_dicts(columns, rows)
    batch_info = batch_info_list[0] if batch_info_list else None

    if batch_info is None:
        return {**_empty, "message": f"No batch found with ID {batch_id}"}

    columns, rows = await execute_query(BATCH_STEPS, (batch_id,), trace_span=trace_span, span_name="batch_steps")
    steps = rows_to_dicts(columns, rows)

    columns, rows = await execute_query(OPERATOR_REMARKS_BY_BATCH, (batch_id,), trace_span=trace_span, span_name="operator_remarks")
    operator_remarks = rows_to_dicts(columns, rows)

    columns, rows = await execute_query(COMPLIANCE_TASKS_BY_BATCH, (batch_id,), trace_span=trace_span, span_name="compliance_tasks")
    compliance_tasks = rows_to_dicts(columns, rows)

    completed_tasks = sum(1 for t in compliance_tasks if t.get("pass_fail") == 1)
    incomplete_task_count = sum(1 for t in compliance_tasks if t.get("pass_fail") == -1)
    problem_remarks = [
        r for r in operator_remarks
        if any(
            kw in str(r.get("remark_text") or "").lower()
            for kw in ("fail", "deviat", "not check", "missing", "abort", "issue", "error", "wrong", "clean")
        )
    ]

    logger.info(
        "get_batch_details → batch_id=%s | steps=%d | remarks=%d | tasks=%d",
        batch_id, len(steps), len(operator_remarks), len(compliance_tasks),
    )

    return {
        "batch_info":       batch_info,
        "steps":            steps,
        "steps_count":      len(steps),
        "operator_remarks": operator_remarks,
        "remarks_count":    len(operator_remarks),
        "compliance_tasks": compliance_tasks,
        "tasks_count":      len(compliance_tasks),
        "incomplete_tasks": incomplete_task_count,
        "methodology": {
            "approach": "Full batch drill-down across four independent data sections",
            "signals_checked": [
                "Batch header: core info from tBatch joined with tJob, tProduct, tSystem",
                f"Steps: {len(steps)} execution steps from tBatchStep + tFunctionDefinition",
                f"Operator remarks: {len(operator_remarks)} free-text notes from _DBR"
                + (f" — {len(problem_remarks)} contain problem keywords" if problem_remarks else " — no problem keywords detected"),
                f"Compliance tasks: {len(compliance_tasks)} from tTask "
                f"({completed_tasks} completed, {incomplete_task_count} incomplete)",
            ],
            "verdict_logic": (
                "Each section is independent — clean parameters do not mean tasks were completed. "
                "Check all four sections for a complete picture of what happened during this batch."
            ),
            "data_sources": ["tBatch", "tJob", "tProduct", "tSystem", "tBatchStep", "tFunctionDefinition", "_DBR", "tTask", "tTaskDefinition"],
            "coverage": (
                f"batch_id={batch_id}: {len(steps)} steps, "
                f"{len(operator_remarks)} operator notes, "
                f"{len(compliance_tasks)} compliance tasks"
            ),
        },
    }


async def get_batch_quality_analysis(
        batch_id: int | None = None,
        batch_name: str | None = None,
        product_name: str | None = None,
        system_id: int | None = None,
        system_name: str | None = None,
        time_window: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
        time_service: TimeResolutionService | None = None,
        trace_span=None,
) -> dict:
    """
    Multi-signal quality analysis for one or more batches.

    Returns three independent quality signals:
        - parameter_deviations: readings outside tParameterDefinition min/max
        - operator_remarks:     free-text root cause notes from _DBR
        - incomplete_tasks:     mandatory compliance tasks not completed (tTask.PassFail = -1)
    """
    safe_limit = max(1, min(int(limit), 1000))

    if batch_name and batch_id is None:
        batch_id = await _resolve_batch_name(batch_name, trace_span)
        if batch_id is None:
            return {
                "parameter_deviations": [], "operator_remarks": [], "incomplete_tasks": [],
                "message": f"No batch found with name/code '{batch_name}'",
            }

    if system_name and system_id is None:
        system_id = await _resolve_system_name(system_name, trace_span)

    time_info = None
    actual_start = start_date
    actual_end = end_date

    if time_window and time_service and batch_id is None:
        resolution = await time_service.resolve(time_window, table="tBatch")
        time_info = resolution
        actual_start = resolution["actual"]["start"]
        actual_end = resolution["actual"]["end"]

    # Shared batch filter reused across all three signal queries
    batch_where: list[str] = []
    batch_params: list[Any] = []

    if batch_id is not None:
        batch_where.append("b.ID = ?")
        batch_params.append(batch_id)
    else:
        if actual_start:
            batch_where.append("b.StartDateTime >= ?")
            batch_params.append(actual_start)
        if actual_end:
            batch_where.append("b.EndDateTime <= ?")
            batch_params.append(actual_end)

    if product_name:
        batch_where.append("p.Name = ?")
        batch_params.append(product_name)
    if system_id is not None:
        batch_where.append("b.SystemID = ?")
        batch_params.append(system_id)

    batch_filter = " AND ".join(batch_where) if batch_where else "1=1"
    batch_params_tuple = tuple(batch_params)

    columns, rows = await execute_query(
        build_quality_deviations_query(safe_limit, batch_filter),
        batch_params_tuple, trace_span=trace_span, span_name="parameter_deviations",
    )
    parameter_deviations = rows_to_dicts(columns, rows)

    columns, rows = await execute_query(
        build_quality_remarks_query(safe_limit, batch_filter),
        batch_params_tuple, trace_span=trace_span, span_name="quality_remarks",
    )
    operator_remarks = rows_to_dicts(columns, rows)

    columns, rows = await execute_query(
        build_quality_incomplete_tasks_query(safe_limit, batch_filter),
        batch_params_tuple, trace_span=trace_span, span_name="incomplete_tasks",
    )
    incomplete_tasks = rows_to_dicts(columns, rows)

    logger.info(
        "get_batch_quality_analysis → deviations=%d | remarks=%d | incomplete_tasks=%d (batch_id=%s, product=%s)",
        len(parameter_deviations), len(operator_remarks), len(incomplete_tasks), batch_id, product_name,
    )

    result: dict[str, Any] = {
        "parameter_deviations":       parameter_deviations,
        "parameter_deviations_count": len(parameter_deviations),
        "operator_remarks":           operator_remarks,
        "operator_remarks_count":     len(operator_remarks),
        "incomplete_tasks":           incomplete_tasks,
        "incomplete_tasks_count":     len(incomplete_tasks),
        "total_quality_signals":      len(parameter_deviations) + len(operator_remarks) + len(incomplete_tasks),
        "methodology": {
            "approach": "Three-signal quality assessment",
            "signals_checked": [
                f"Parameter readings compared against allowed min/max limits ({len(parameter_deviations)} deviations found)",
                f"Operator notes scanned for problem keywords ({len(operator_remarks)} remarks reviewed)",
                f"Mandatory compliance tasks checked for completion ({len(incomplete_tasks)} incomplete tasks found)",
            ],
            "verdict_logic": "Batch flagged if any single signal triggers",
            "data_sources": ["tBatchParameter vs tParameterDefinition", "_DBR operator notes", "tTask compliance records"],
        },
    }

    if time_info:
        result["time_info"] = time_info

    return result