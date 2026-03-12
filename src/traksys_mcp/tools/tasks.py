import logging
from typing import TYPE_CHECKING

from src.traksys_mcp.models.tool_outputs import ToolResponse, TimeResolutionInfo
from src.traksys_mcp.services import tasks
from src.traksys_mcp.models.tool_inputs import GetBatchTasksInput, AnalyzeTaskComplianceInput
from src.traksys_mcp.tools.batches import _build_response

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from src.traksys_mcp.services.time_resolution import TimeResolutionService
    from src.traksys_mcp.services.langfuse_tracing import TracingService


class TaskTools:
    """Task compliance MCP tools."""

    def __init__(self, mcp: "FastMCP", time_service: "TimeResolutionService", tracing: "TracingService"):
        self.mcp = mcp
        self.time_service = time_service
        self.tracing = tracing
        self.logger = logging.getLogger(__name__)

    def register(self) -> None:
        self._register_get_batch_tasks()
        self._register_analyze_task_compliance()

    def _register_get_batch_tasks(self) -> None:

        @self.mcp.tool(
            name="get_batch_tasks",
            description=(
                "Retrieve compliance tasks for a batch or time period. "
                "Shows each task with its completion status (Completed/Incomplete/Pending), "
                "assigned operator, and timestamps. "
                "Use this to answer: 'What tasks are assigned to batch 462?', "
                "'Show me all incomplete tasks for this batch', "
                "'Were all compliance tasks completed for batch 473?' "
                "Includes a compliance rate summary (percentage of tasks completed). "
                "Filter by status_filter='incomplete' to focus on failures only."
            ),
        )
        async def get_batch_tasks(params: GetBatchTasksInput) -> dict:
            tool_name = "get_batch_tasks"
            inputs = params.model_dump(exclude_none=True)
            async with self.tracing.trace_tool(tool_name, inputs) as span:
                try:
                    result = await tasks.get_batch_tasks(
                        batch_id=params.batch_id,
                        batch_name=params.batch_name,
                        status_filter=params.status_filter,
                        task_name=params.task_name,
                        time_window=params.time_window,
                        start_date=params.start_date,
                        end_date=params.end_date,
                        limit=params.limit,
                        time_service=self.time_service,
                        trace_span=span,
                    )
                    time_info_raw = result.get("time_info")
                    time_info = TimeResolutionInfo(**time_info_raw) if time_info_raw else None
                    response = _build_response(
                        data=result.get("tasks") or None,
                        time_info=time_info_raw,
                        no_data_suggestions=[
                            "Try without status_filter to see all tasks",
                            "Check the batch_id is correct",
                            "Try a broader time_window like 'last 30 days'",
                        ],
                    )
                    # _build_response uses the raw dict for fallback check; wrap in model for partial
                    if time_info and time_info_raw.get("fallback_triggered") and result.get("tasks"):
                        response = ToolResponse.partial(
                            data=result,
                            time_info=time_info,
                            message=time_info_raw.get("message", "Time window fallback triggered"),
                        )
                    self.tracing.set_output(span, response.model_dump())
                    return response.to_dict()
                except Exception as exc:
                    self.logger.error("%s failed: %s", tool_name, exc)
                    self.tracing.record_error(span, exc, tool_name)
                    return ToolResponse.error(
                        message=f"Failed to retrieve tasks: {exc}",
                        suggestions=["Check database connection", "Verify batch_id exists"],
                    ).to_dict()

    def _register_analyze_task_compliance(self) -> None:

        @self.mcp.tool(
            name="analyze_task_compliance",
            description=(
                "Analyse compliance task patterns across multiple batches. "
                "Groups results by task type to show which tasks fail most frequently. "
                "Use this to answer: 'Which compliance tasks are most often incomplete?', "
                "'What is the overall compliance rate for line E1?', "
                "'Which tasks have the highest failure rate this month?', "
                "'What are the most common compliance failures for this product?' "
                "Returns a ranked list of task types by failure count, overall compliance rate, "
                "and top failing tasks. "
                "Combine with time_window or system_name to narrow the analysis."
            ),
        )
        async def analyze_task_compliance(params: AnalyzeTaskComplianceInput) -> dict:
            tool_name = "analyze_task_compliance"
            inputs = params.model_dump(exclude_none=True)
            async with self.tracing.trace_tool(tool_name, inputs) as span:
                try:
                    result = await tasks.analyze_task_compliance(
                        system_name=params.system_name,
                        system_id=params.system_id,
                        product_name=params.product_name,
                        time_window=params.time_window,
                        start_date=params.start_date,
                        end_date=params.end_date,
                        limit=params.limit,
                        time_service=self.time_service,
                        trace_span=span,
                    )
                    response = _build_response(
                        data=result.get("compliance_by_task") or None,
                        time_info=result.get("time_info"),
                        no_data_suggestions=[
                            "Try a broader time_window like 'last 30 days'",
                            "Remove system_name or product_name filter",
                            "Check tTask table has data for the requested period",
                        ],
                    )
                    # When data exists, return the full result dict (not just the list)
                    if result.get("compliance_by_task"):
                        response = ToolResponse.success(data=result)
                    self.tracing.set_output(span, response.model_dump())
                    return response.to_dict()
                except Exception as exc:
                    self.logger.error("%s failed: %s", tool_name, exc)
                    self.tracing.record_error(span, exc, tool_name)
                    return ToolResponse.error(
                        message=f"Failed to analyse task compliance: {exc}",
                        suggestions=["Check database connection", "Try without filters first"],
                    ).to_dict()