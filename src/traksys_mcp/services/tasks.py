import logging
from typing import Any

from src.traksys_mcp.core.database import execute_query
from src.traksys_mcp.core.utils import rows_to_dicts
from src.traksys_mcp.services.time_resolution import TimeResolutionService
from src.traksys_mcp.utils.tasks_queries import (
    build_batch_tasks_query,
    build_compliance_by_task_query,
    build_compliance_totals_query,
)
from src.traksys_mcp.utils.batch_queries import BATCH_NAME_LOOKUP, SYSTEM_NAME_LOOKUP

logger = logging.getLogger(__name__)

_SKIP_TIME = {"all", "any", "everything", "all time", "alltime"}


async def get_batch_tasks(
    batch_id: int | None = None,
    batch_name: str | None = None,
    status_filter: str | None = None,
    task_name: str | None = None,
    time_window: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
    time_service: TimeResolutionService | None = None,
    trace_span=None,
) -> dict:
    """Retrieve compliance tasks for one or more batches."""
    safe_limit = max(1, min(int(limit), 1000))

    if batch_name and batch_id is None:
        _, rows = await execute_query(
            BATCH_NAME_LOOKUP,
            (batch_name, batch_name, batch_name),
            trace_span=trace_span,
            span_name="batch_name_lookup",
        )
        if rows and rows[0][0]:
            batch_id = rows[0][0]
            logger.info("Resolved batch_name '%s' → ID %s", batch_name, batch_id)
        else:
            return {"tasks": [], "count": 0, "message": f"No batch found with name/code '{batch_name}'"}

    time_info = None
    actual_start = start_date
    actual_end = end_date

    # FIX: Only call time_service.resolve() if time_window is truthy
    if time_window and time_service and batch_id is None and time_window.lower().strip() not in _SKIP_TIME:
        resolution = await time_service.resolve(time_window, table="tBatch")
        time_info = resolution
        actual_start = resolution["actual"]["start"]
        actual_end = resolution["actual"]["end"]

    where_parts: list[str] = []
    params: list[Any] = []

    if batch_id is not None:
        where_parts.append("t.BatchID = ?")
        params.append(batch_id)
    else:
        if actual_start:
            where_parts.append("b.StartDateTime >= ?")
            params.append(actual_start)
        if actual_end:
            where_parts.append("b.EndDateTime <= ?")
            params.append(actual_end)

    if task_name:
        where_parts.append("td.Name LIKE ?")
        params.append(f"%{task_name}%")

    if status_filter:
        s = status_filter.lower()
        if s == "completed":
            where_parts.append("t.PassFail = 1")
        elif s == "incomplete":
            where_parts.append("t.PassFail = -1")
        elif s == "pending":
            where_parts.append("t.PassFail = 0")

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"

    columns, rows = await execute_query(
        build_batch_tasks_query(safe_limit, where_clause),
        tuple(params),
        trace_span=trace_span,
        span_name="batch_tasks_main",
    )
    tasks = rows_to_dicts(columns, rows)

    completed = sum(1 for t in tasks if t.get("pass_fail") == 1)
    incomplete = sum(1 for t in tasks if t.get("pass_fail") == -1)
    pending = sum(1 for t in tasks if t.get("pass_fail") not in (1, -1))
    compliance_rate = round((completed / len(tasks) * 100), 1) if tasks else 0.0

    logger.info(
        "get_batch_tasks → %d tasks (batch_id=%s, status=%s) completed=%d incomplete=%d",
        len(tasks), batch_id, status_filter, completed, incomplete,
    )

    result: dict[str, Any] = {
        "tasks": tasks,
        "count": len(tasks),
        "summary": {
            "completed": completed,
            "incomplete": incomplete,
            "pending": pending,
            "compliance_rate_pct": compliance_rate,
        },
        "methodology": {
            "approach": "Compliance task retrieval from tTask",
            "signals_checked": [
                f"Tasks retrieved from tTask joined with tTaskDefinition ({len(tasks)} tasks found)",
                f"Completion status derived from PassFail field: 1=Completed, -1=Incomplete, 0=Pending",
                f"Compliance rate: {compliance_rate}% ({completed} of {len(tasks)} tasks completed)",
            ],
            "verdict_logic": "Each task is independently assessed — no aggregation across batches unless time window provided",
            "data_sources": ["tTask", "tTaskDefinition", "tBatch", "tSystem", "tProduct"],
        },
    }

    if time_info:
        result["time_info"] = time_info

    return result

async def analyze_task_compliance(
        system_name: str | None = None,
        system_id: int | None = None,
        product_name: str | None = None,
        time_window: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
        time_service: TimeResolutionService | None = None,
        trace_span=None,
) -> dict:
    """
    Analyse compliance task patterns across batches.
    Groups by task name to show failure frequency ranking.
    """
    safe_limit = max(1, min(int(limit), 1000))

    if system_name and system_id is None:
        _, rows = await execute_query(
            SYSTEM_NAME_LOOKUP, (system_name,),
            trace_span=trace_span, span_name="system_name_lookup",
        )
        if rows and rows[0][0]:
            system_id = rows[0][0]
            logger.info("Resolved system_name '%s' → ID %s", system_name, system_id)

    time_info = None
    actual_start = start_date
    actual_end = end_date

    if time_window and time_service and time_window.lower().strip() not in _SKIP_TIME:
        resolution = await time_service.resolve(time_window, table="tBatch")
        time_info = resolution
        actual_start = resolution["actual"]["start"]
        actual_end = resolution["actual"]["end"]

    where_parts: list[str] = []
    params: list[Any] = []

    if actual_start:
        where_parts.append("b.StartDateTime >= ?")
        params.append(actual_start)
    if actual_end:
        where_parts.append("b.EndDateTime <= ?")
        params.append(actual_end)
    if system_id is not None:
        where_parts.append("b.SystemID = ?")
        params.append(system_id)
    if product_name:
        where_parts.append("p.Name = ?")
        params.append(product_name)

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"
    params_tuple = tuple(params)

    columns, rows = await execute_query(
        build_compliance_by_task_query(safe_limit, where_clause),
        params_tuple,
        trace_span=trace_span,
        span_name="compliance_by_task",
    )
    by_task = rows_to_dicts(columns, rows)

    columns, rows = await execute_query(
        build_compliance_totals_query(where_clause),
        params_tuple,
        trace_span=trace_span,
        span_name="compliance_totals",
    )
    totals_list = rows_to_dicts(columns, rows)
    totals = totals_list[0] if totals_list else {}

    total_tasks = totals.get("total_tasks") or 0
    total_completed = totals.get("total_completed") or 0
    total_incomplete = totals.get("total_incomplete") or 0
    batches_covered = totals.get("batches_covered") or 0
    overall_rate = round((total_completed / total_tasks * 100), 1) if total_tasks else 0.0

    top_failing = [t for t in by_task if (t.get("incomplete_count") or 0) > 0][:5]

    logger.info(
        "analyze_task_compliance → %d task types | overall_rate=%.1f%% | batches=%d",
        len(by_task), overall_rate, batches_covered,
    )

    result: dict[str, Any] = {
        "compliance_by_task": by_task,
        "task_types_count": len(by_task),
        "overall_summary": {
            "total_tasks": total_tasks,
            "total_completed": total_completed,
            "total_incomplete": total_incomplete,
            "overall_compliance_rate_pct": overall_rate,
            "batches_covered": batches_covered,
        },
        "top_failing_tasks": top_failing,
        "methodology": {
            "approach": "Task compliance frequency analysis across batches",
            "signals_checked": [
                f"Analysed {total_tasks} task assignments across {batches_covered} batches",
                f"Grouped by task type to identify which tasks fail most frequently",
                f"Overall compliance rate: {overall_rate}% ({total_completed} completed of {total_tasks} total)",
                f"Top {len(top_failing)} failing task types identified by incomplete count",
            ],
            "verdict_logic": "Task types ranked by incomplete_count descending — highest failure rate first",
            "data_sources": ["tTask", "tTaskDefinition", "tBatch", "tSystem", "tProduct"],
        },
    }

    if time_info:
        result["time_info"] = time_info

    return result