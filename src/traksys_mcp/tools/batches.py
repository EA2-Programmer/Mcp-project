import logging
from typing import TYPE_CHECKING

from src.traksys_mcp.models.tool_outputs import ToolResponse
from src.traksys_mcp.services import batches
from src.traksys_mcp.models.tool_inputs import (
    GetBatchesInput,
    GetBatchParametersInput,
    GetBatchMaterialsInput,
    GetBatchDetailsInput,
    GetBatchQualityAnalysisInput,
)

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from src.traksys_mcp.services.time_resolution import TimeResolutionService
    from src.traksys_mcp.services.langfuse_tracing import TracingService


def _build_response(data, time_info, no_data_suggestions: list[str]) -> ToolResponse:
    """Return no_data / partial / success based on data presence and fallback state."""
    if not data:
        return ToolResponse.no_data(suggestions=no_data_suggestions, time_info=time_info)
    if time_info and time_info.get("fallback_triggered"):
        return ToolResponse.partial(data=data, time_info=time_info, message=time_info.get("message"))
    return ToolResponse.success(data=data, time_info=time_info)


class BatchTools:
    """Batch-related MCP tools with tracing and time resolution injected."""

    def __init__(self, mcp: "FastMCP", time_service: "TimeResolutionService", tracing: "TracingService"):
        self.mcp = mcp
        self.time_service = time_service
        self.tracing = tracing
        self.logger = logging.getLogger(__name__)

    def register(self) -> None:
        self._register_get_batches()
        self._register_get_batch_parameters()
        self._register_get_batch_materials()
        self._register_get_batch_details()
        self._register_get_batch_quality_analysis()

    def _register_get_batches(self) -> None:

        @self.mcp.tool(
            name="get_batches",
            description="""Query production batches with flexible filtering and time intelligence.

**Use this tool when the user asks about:**
- "Show me all batches from yesterday"
- "What batches ran on line E1 last week?"
- "Find batch AA001"
- "List batches for product P00001 this month"
- "Show me all batches in September"
- "Which batches ran more than 4 hours?"
- "How many batches completed last week?"

**No batch ID required** — omit batch_id and batch_name to query across a time window or line.

**Key Parameters:**
- `time_window`: Natural language time (e.g., 'yesterday', 'last 7 days')
- `batch_name`: Human-readable batch code (e.g., 'AA001') — optional
- `system_name`: Filter by production line name (e.g., 'E1') — optional
"""
        )
        async def get_batches(params: GetBatchesInput) -> dict:
            inputs = params.model_dump()
            async with self.tracing.trace_tool("get_batches", inputs) as span:
                try:
                    result = await batches.get_batches(
                        time_service=self.time_service, trace_span=span, **inputs,
                    )
                    response = _build_response(
                        data=result["batches"],
                        time_info=result.get("time_info"),
                        no_data_suggestions=[
                            "Try a broader time_window like 'last 30 days'",
                            "Verify the batch_name or batch_id is correct",
                            "Check if the system_id matches a valid production line",
                        ],
                    )
                    self.tracing.set_output(span, response.to_dict())
                    return response.to_dict()
                except Exception as e:
                    self.tracing.record_error(span, e, "get_batches")
                    self.logger.error("get_batches failed: %s", e, exc_info=True)
                    return ToolResponse.error(
                        message=str(e),
                        suggestions=[
                            "Check the database connection",
                            "Verify time_window format (e.g., 'last 7 days')",
                            "Try with just a batch_name or batch_id",
                        ],
                    ).to_dict()

    def _register_get_batch_parameters(self) -> None:

        @self.mcp.tool(
            name="get_batch_parameters",
            description="""Retrieve process parameters (temperature, pressure, speed, etc.) recorded during a batch.

**Use this tool when the user asks about:**
- "What were the process parameters for batch AA001?"
- "Show me any out-of-spec readings for last week's batches"
- "Were there any temperature deviations on line E1 yesterday?"
- "Show me all parameter deviations in September"
- "Which parameters were out of spec last month?"

**No batch ID required** — use time_window to query across a date range without specifying a batch.

**Key Parameters:**
- `deviation_only`: True returns only out-of-spec readings
- `parameter_names`: Filter to specific parameters (e.g., ['Temperature', 'Pressure'])
- `time_window`: Natural language time (e.g., 'last 7 days')
"""
        )
        async def get_batch_parameters(params: GetBatchParametersInput) -> dict:
            inputs = params.model_dump()
            async with self.tracing.trace_tool("get_batch_parameters", inputs) as span:
                try:
                    result = await batches.get_batch_parameters(
                        time_service=self.time_service, trace_span=span, **inputs,
                    )
                    response = _build_response(
                        data=result["parameters"],
                        time_info=result.get("time_info"),
                        no_data_suggestions=[
                            "Verify the batch_id or batch_name is correct",
                            "Try without deviation_only=true to see all parameters",
                            "Check if parameter_names match exact names in tParameterDefinition",
                        ],
                    )
                    self.tracing.set_output(span, response.to_dict())
                    return response.to_dict()
                except Exception as e:
                    self.tracing.record_error(span, e, "get_batch_parameters")
                    self.logger.error("get_batch_parameters failed: %s", e, exc_info=True)
                    return ToolResponse.error(
                        message=str(e),
                        suggestions=[
                            "Verify the batch_id or batch_name",
                            "Check if tBatchParameter table is accessible",
                        ],
                    ).to_dict()

    def _register_get_batch_materials(self) -> None:

        @self.mcp.tool(
            name="get_batch_materials",
            description="""Retrieve actual material consumption/usage for a batch or date range.

**Use this tool when the user asks about:**
- "What materials were used in batch AA001?"
- "How much Sugar was consumed last week?"
- "Show material usage for job 12345"
- "What materials were consumed last week across all batches?"
- "Show me all material usage in September"

**No batch ID required** — use time_window to query consumption across a date range.

**Key Parameters:**
- `batch_name` or `batch_id`: Identifies the batch — both optional
- `time_window`: Natural language time (e.g., 'last 7 days')
- `material_names`: Filter to specific materials (e.g., ['Sugar', 'Water'])
- `material_codes`: Filter by material codes (e.g., ['MAT-001'])

**Note on units:** Quantities are in KGR (Kilogram Reactive — pharmaceutical unit, not standard KG).
**Note on silos:** Silo source not available yet (SAP integration pending).
"""
        )
        async def get_batch_materials(params: GetBatchMaterialsInput) -> dict:
            inputs = params.model_dump()
            async with self.tracing.trace_tool("get_batch_materials", inputs) as span:
                try:
                    result = await batches.get_batch_materials(
                        time_service=self.time_service, trace_span=span, **inputs,
                    )
                    response = _build_response(
                        data=result["materials"],
                        time_info=result.get("time_info"),
                        no_data_suggestions=[
                            "Verify the batch_id, batch_name, or job_id is correct",
                            "Check if tMaterialUseActual has records for this batch",
                            "Try without material_names filter to see all materials",
                        ],
                    )
                    self.tracing.set_output(span, response.to_dict())
                    return response.to_dict()
                except Exception as e:
                    self.tracing.record_error(span, e, "get_batch_materials")
                    self.logger.error("get_batch_materials failed: %s", e, exc_info=True)
                    return ToolResponse.error(
                        message=str(e),
                        suggestions=[
                            "Ensure batch_id, batch_name, or job_id is provided",
                            "Check tMaterialUseActual table accessibility",
                        ],
                    ).to_dict()

    def _register_get_batch_details(self) -> None:

        @self.mcp.tool(
            name="get_batch_details",
            description="""Get complete drill-down for a single batch: steps, operator remarks, and compliance tasks.

**Use this tool when the user asks about:**
- "Give me the full details for batch AA001"
- "What steps were executed in batch 42?"
- "Were all compliance tasks completed for this batch?"
- "What did operators note during batch AA001?"

**Returns four sections:**
- `batch_info`: Core batch, job, product, and line data
- `steps`: Every step executed with start/end times and duration
- `operator_remarks`: Free-text notes entered by operators during the batch
- `compliance_tasks`: Mandatory tasks and their pass/fail status
"""
        )
        async def get_batch_details(params: GetBatchDetailsInput) -> dict:
            inputs = params.model_dump()
            async with self.tracing.trace_tool("get_batch_details", inputs) as span:
                try:
                    result = await batches.get_batch_details(trace_span=span, **inputs)
                    response = (
                        ToolResponse.no_data(
                            suggestions=[
                                "Verify the batch_id or batch_name is correct",
                                "Try get_batches first to find valid batch IDs",
                            ]
                        )
                        if not result.get("batch_info")
                        else ToolResponse.success(data=result)
                    )
                    self.tracing.set_output(span, response.to_dict())
                    return response.to_dict()
                except Exception as e:
                    self.tracing.record_error(span, e, "get_batch_details")
                    self.logger.error("get_batch_details failed: %s", e, exc_info=True)
                    return ToolResponse.error(
                        message=str(e),
                        suggestions=[
                            "Verify the batch_id or batch_name is correct",
                            "Ensure tBatchStep, _DBR, and tTask tables are accessible",
                        ],
                    ).to_dict()

    def _register_get_batch_quality_analysis(self) -> None:

        @self.mcp.tool(
            name="get_batch_quality_analysis",
            description="""Diagnoses quality issues for one or more batches using three independent signals.

**METHODOLOGY — How quality is assessed:**

Signal 1 — Parameter Deviations:
Compares every recorded value in tBatchParameter against the min/max
limits defined in tParameterDefinition. A parameter is flagged as
deviated if its value falls outside these bounds.

Signal 2 — Operator Remarks:
Scans free-text notes recorded by operators in the _DBR table.
Looks for keywords indicating problems (e.g. 'failed', 'deviation',
'not checked', 'equipment issue').

Signal 3 — Incomplete Mandatory Tasks:
Checks tTask for compliance steps that were required but not completed.

**A batch is flagged as problematic if ANY of the three signals triggers.**

**Use this tool when the user asks:**
- "Were there any quality issues with batch 462?"
- "Why was batch 457 flagged?"
- "Show me all batches with parameter deviations last week"
- "Which batches had incomplete tasks in September?"
- "What caused the quality problems on line E1?"

**Key Parameters:**
- `batch_id`: Single batch deep-dive
- `time_window`: Analyse quality trends over a period (e.g. 'last 30 days')
- `system_name`: Filter by production line (e.g. 'E1')
- `limit`: Controls records per signal type independently
"""
        )
        async def get_batch_quality_analysis(params: GetBatchQualityAnalysisInput) -> dict:
            inputs = params.model_dump()
            async with self.tracing.trace_tool("get_batch_quality_analysis", inputs) as span:
                try:
                    result = await batches.get_batch_quality_analysis(
                        time_service=self.time_service, trace_span=span, **inputs,
                    )
                    response = _build_response(
                        data=result if result.get("total_quality_signals", 0) > 0 else None,
                        time_info=result.get("time_info"),
                        no_data_suggestions=[
                            "No quality signals found — this batch may have run cleanly",
                            "Try a broader time_window or different product_name",
                            "Verify batch_id or batch_name is correct",
                        ],
                    )
                    # When there are signals but no fallback, success needs the full result
                    if result.get("total_quality_signals", 0) > 0 and not (
                        result.get("time_info") and result["time_info"].get("fallback_triggered")
                    ):
                        response = ToolResponse.success(data=result, time_info=result.get("time_info"))
                    self.tracing.set_output(span, response.to_dict())
                    return response.to_dict()
                except Exception as e:
                    self.tracing.record_error(span, e, "get_batch_quality_analysis")
                    self.logger.error("get_batch_quality_analysis failed: %s", e, exc_info=True)
                    return ToolResponse.error(
                        message=str(e),
                        suggestions=[
                            "Check that tBatchParameter, _DBR, and tTask are accessible",
                            "Verify product_name matches exactly (case-sensitive)",
                        ],
                    ).to_dict()