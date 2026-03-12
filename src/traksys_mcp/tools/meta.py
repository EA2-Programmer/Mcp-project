import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from src.traksys_mcp.services.langfuse_tracing import TracingService


TOOL_EXPLANATIONS = {
    "get_batches": {
        "purpose": "Query production batches from the TrakSYS database with flexible filtering.",
        "methodology": [
            "Queries the tBatch table joined with tJob, tSystem (production line), and tProduct.",
            "Supports filtering by batch ID, batch name, system/line, job ID, state, and time window.",
            "Natural language time expressions (e.g. 'last 7 days', 'yesterday') are resolved via TimeResolutionService.",
            "If no data exists for the requested time window, the system automatically falls back to the nearest available data range.",
            "Batch name is resolved to a numeric ID automatically — you can provide a short code or a full batch name.",
        ],
        "data_sources": ["tBatch", "tJob", "tSystem", "tProduct"],
        "output_fields": [
            "batch_id, batch_name — batch identity",
            "system_name — production line (e.g. E1)",
            "product_name — product being manufactured",
            "start_time, end_time — batch duration",
            "state — batch status (e.g. Completed, In Progress)",
            "actual_batch_size, planned_batch_size — output quantities",
        ],
        "limitations": [
            "ActualBatchSize is currently 0 for all batches — known data gap in the demo environment.",
            "Time fallback is triggered when no data exists in the requested period.",
        ],
    },

    "get_batch_parameters": {
        "purpose": "Retrieve process parameter readings recorded during a batch, with optional deviation detection.",
        "methodology": [
            "Queries tBatchParameter for all recorded parameter values during the batch.",
            "Joins tParameterDefinition to get the allowed min/max range for each parameter.",
            "When deviation_only=True, filters to only return readings where the value is outside the min/max bounds.",
            "Deviation is calculated as: value < MinValue OR value > MaxValue (from tParameterDefinition).",
            "Supports _CPR table for extended deviation logic (L_PAR, L_NOR, H_NOR, H_PAR) if configured.",
        ],
        "data_sources": ["tBatchParameter", "tParameterDefinition", "_CPR"],
        "output_fields": [
            "parameter_name — name of the process parameter",
            "value — recorded reading",
            "min_value, max_value — allowed range from tParameterDefinition",
            "is_deviation — True if value is outside min/max bounds",
            "recorded_at — timestamp of the reading",
            "step_name — which batch step this reading belongs to",
        ],
        "limitations": [
            "Deviation detection requires min/max limits to be configured in tParameterDefinition.",
            "If limits are NULL, no deviation can be detected for that parameter.",
        ],
    },

    "get_batch_materials": {
        "purpose": "Retrieve actual material consumption recorded during a batch.",
        "methodology": [
            "Queries tMaterialUseActual for all material usage records.",
            "The link between a batch and its materials goes through tJob: tBatch.JobID → tJob.ID → tMaterialUseActual.JobID.",
            "Joins tMaterial to get the material name, code, and units.",
            "Supports filtering by material name or material code.",
            "Returns each individual consumption record — multiple records for the same material mean it was added in multiple doses.",
        ],
        "data_sources": ["tMaterialUseActual", "tMaterialUsePlanned", "tMaterial", "tBatch", "tJob"],
        "output_fields": [
            "material_name, material_code — material identity",
            "quantity, units — amount consumed (e.g. 1.5 KG)",
            "lot, sublot — traceability information",
            "recorded_at — when the consumption was logged",
            "recorded_by — operator who recorded the usage",
        ],
        "limitations": [
            "Material names in the demo environment are generic (Material 1, Material 2 etc.).",
        ],
    },

    "get_batch_details": {
        "purpose": "Full drill-down for a single batch — steps, operator remarks, and compliance tasks.",
        "methodology": [
            "Retrieves batch core info from tBatch joined with tJob, tSystem, tProduct.",
            "Fetches all batch steps from tBatchStep with start/end times and duration.",
            "Retrieves operator remarks from the _DBR table (Digital Batch Record) — free-text notes entered by operators during the batch.",
            "Checks tTask for all mandatory compliance tasks and their completion status.",
            "Returns all four sections in a single response for a complete batch picture.",
        ],
        "data_sources": ["tBatch", "tJob", "tSystem", "tProduct", "tBatchStep", "_DBR", "tTask"],
        "output_fields": [
            "batch_info — core batch, job, product, and line data",
            "steps — every step with start/end times and duration",
            "operator_remarks — free-text notes from _DBR",
            "compliance_tasks — mandatory tasks with pass/fail status",
        ],
        "limitations": [
            "Requires either batch_id or batch_name to be provided.",
            "_DBR remarks are free-text — content quality depends on what operators entered.",
        ],
    },

    "get_batch_quality_analysis": {
        "purpose": "Diagnose quality issues for one or more batches using three independent signals.",
        "methodology": [
            "Signal 1 — Parameter Deviations: Compares every recorded value in tBatchParameter against "
            "the min/max limits in tParameterDefinition. Flags readings outside bounds.",

            "Signal 2 — Operator Remarks: Scans free-text notes in the _DBR table for keywords "
            "indicating problems (e.g. 'failed', 'deviation', 'not checked', 'equipment issue').",

            "Signal 3 — Incomplete Mandatory Tasks: Checks tTask for compliance steps that were "
            "required but not completed.",

            "A batch is flagged as problematic if ANY of the three signals triggers.",
        ],
        "data_sources": ["tBatch", "tBatchParameter", "tParameterDefinition", "_DBR", "tTask"],
        "output_fields": [
            "total_quality_signals — total count of issues across all three signals",
            "parameter_deviations — list of out-of-spec parameter readings",
            "operator_remarks — flagged operator notes containing problem keywords",
            "incomplete_tasks — mandatory tasks that were not completed",
        ],
        "limitations": [
            "Parameter deviation detection requires min/max limits in tParameterDefinition.",
            "Operator remark scanning uses keyword matching — nuanced remarks may be missed.",
        ],
    },

    "get_equipment_state": {
        "purpose": "Get real-time status, availability, and performance metrics for manufacturing equipment.",
        "methodology": [
            "Queries tSystem for all equipment, filtering by system_id, system_name, or area_id.",
            "Determines current status (Running/Idle) by checking for open records in tJobSystemActual (EndDateTime IS NULL = currently running).",
            "When include_tags=True, fetches live tag values from tTag (speed, counts, product codes).",
            "When include_oee=True, calculates runtime metrics from tJobSystemActual for the requested period.",
            "OEE availability proxy = total runtime / total period duration (true OEE requires additional Performance and Quality data).",
        ],
        "data_sources": ["tSystem", "tJobSystemActual", "tTag"],
        "output_fields": [
            "system_id, system_name — equipment identity",
            "status — Running or Idle",
            "current_job_id — active job if running",
            "session_start — when current run started",
            "performance_metrics — runtime minutes and session count (if include_oee=True)",
            "actual_count, current_product, current_batch — live tag values (if include_tags=True)",
        ],
        "limitations": [
            "OEE calculation is a proxy using runtime only — true OEE requires Performance and Quality data.",
            "Live tags require tTag to be configured and connected to a real data source.",
        ],
    },
}

AVAILABLE_TOOLS = list(TOOL_EXPLANATIONS.keys())


class GetToolExplanationInput(BaseModel):
    tool_name: str = Field(
        description=(
            "Name of the tool to explain. "
            f"Available tools: {', '.join(AVAILABLE_TOOLS)}. "
            "Use 'all' to list all available tools and their purposes."
        )
    )


class MetaTools:
    """Meta tools — let users and the LLM query the server's own methodology and data sources."""

    def __init__(self, mcp: "FastMCP", tracing: "TracingService"):
        self.mcp = mcp
        self.tracing = tracing
        self.logger = logging.getLogger(__name__)

    def register(self) -> None:
        self._register_get_tool_explanation()

    def _register_get_tool_explanation(self) -> None:

        @self.mcp.tool(
            name="get_tool_explanation",
            description="""Explains the methodology, data sources, and logic behind any TrakSYS MCP tool.

Use this tool when the user asks:
- "How does the quality analysis work?"
- "What data sources does the materials tool use?"
- "How do you detect parameter deviations?"
- "What tools are available?"

Returns the exact methodology — not an interpretation. Use tool_name='all' to list all tools.
"""
        )
        async def get_tool_explanation(params: GetToolExplanationInput) -> dict:
            inputs = params.model_dump()
            async with self.tracing.trace_tool("get_tool_explanation", inputs) as span:
                try:
                    tool_name = params.tool_name.strip().lower()

                    if tool_name == "all":
                        result = {
                            "available_tools": [
                                {"tool_name": name, "purpose": info["purpose"]}
                                for name, info in TOOL_EXPLANATIONS.items()
                            ],
                            "total": len(TOOL_EXPLANATIONS),
                            "usage_hint": "Call get_tool_explanation with a specific tool_name to get full methodology details.",
                        }
                    elif tool_name not in TOOL_EXPLANATIONS:
                        result = {
                            "error": f"Unknown tool: '{tool_name}'",
                            "available_tools": AVAILABLE_TOOLS,
                            "suggestion": f"Try one of: {', '.join(AVAILABLE_TOOLS)} or use 'all'",
                        }
                    else:
                        result = {"tool_name": tool_name, **TOOL_EXPLANATIONS[tool_name]}

                    self.tracing.set_output(span, result)
                    return result

                except Exception as e:
                    self.tracing.record_error(span, e, "get_tool_explanation")
                    self.logger.error("get_tool_explanation failed: %s", e, exc_info=True)
                    return {"error": str(e), "available_tools": AVAILABLE_TOOLS}