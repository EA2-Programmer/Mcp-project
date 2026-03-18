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
            "start_datetime, end_datetime — batch duration",
            "state — batch status (3=Completed, 5=Aborted)",
            "recipe_id — the recipe used for this batch (use get_recipe to look up details)",
            "job_id, job_name — the production order this batch belongs to",
            "planned_batch_size — target quantity in KGR",
        ],
        "limitations": [
            "ActualBatchSize is currently 0 for all batches — known data gap in the demo environment.",
            "Time fallback is triggered when no data exists in the requested period.",
            "Only shows products that have been used in production — use get_products for all products including unused ones.",
        ],
    },

    "get_batch_parameters": {
        "purpose": "Retrieve process parameter readings recorded during a batch, with optional deviation detection.",
        "methodology": [
            "Queries tBatchParameter for all recorded parameter values during the batch.",
            "Joins tParameterDefinition to get the allowed min/max range for each parameter.",
            "When deviation_only=True, filters to only return readings where the value is outside the min/max bounds.",
            "Deviation is calculated as: value < MinimumValue OR value > MaximumValue (from tParameterDefinition).",
            "Supports _CPR table for extended deviation logic (L_PAR, L_NOR, H_NOR, H_PAR) if configured.",
        ],
        "data_sources": ["tBatchParameter", "tParameterDefinition", "_CPR"],
        "output_fields": [
            "parameter_name — name of the process parameter (e.g. Filling Weight, Temperature batch, Amount, Agitation Speed)",
            "value_raw, value_numeric — recorded reading",
            "min_allowed, max_allowed — allowed range from tParameterDefinition",
            "is_deviation — 1 if value is outside min/max bounds",
            "batch_id, batch_name — which batch this reading belongs to",
        ],
        "limitations": [
            "Deviation detection requires min/max limits to be configured in tParameterDefinition.",
            "If limits are NULL, no deviation can be detected for that parameter.",
            "Parameters in this system: Filling Weight (min=10, max=20), Temperature batch (min=10, max=15), Amount (min=10, max=20), Agitation Speed (min=-9999, max=9999).",
        ],
    },

    "get_batch_materials": {
        "purpose": "Retrieve actual RAW MATERIAL consumption recorded during a batch. DO NOT use for finished products.",
        "methodology": [
            "Queries tMaterialUseActual for all material usage records.",
            "The link between a batch and its materials goes through tJob: tBatch.JobID → tJob.ID → tMaterialUseActual.JobID.",
            "Joins tMaterial to get the material name, code, and units.",
            "Also fetches planned BOM from _SAPBOM when include_planned_bom=True (default).",
            "Returns each individual consumption record — multiple records for the same material mean it was added in multiple doses.",
        ],
        "data_sources": ["tMaterialUseActual", "_SAPBOM", "tMaterial", "tBatch", "tJob"],
        "output_fields": [
            "actual_consumption — list of actual material usage records",
            "planned_bom — planned BOM lines from _SAPBOM (quantities in KG)",
            "material_name, material_code — material identity (e.g. Material 1/M1, Material 3/M3, Material 4/M4)",
            "consumed_quantity — amount used in KGR",
        ],
        "limitations": [
            "Returns actual_consumption key (not 'materials') — planned vs actual comparison available.",
            "Actual quantities in KGR, planned quantities in KG — not directly comparable.",
            "Only 3 distinct materials in this system: M1 (Material 1), M3 (Material 3), M4 (Material 4).",
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
        "data_sources": ["tBatch", "tJob", "tSystem", "tProduct", "tBatchStep", "tFunctionDefinition", "_DBR", "tTask", "tTaskDefinition"],
        "output_fields": [
            "batch_info — core batch, job, product, and line data",
            "steps — every step with start/end times and duration_seconds",
            "steps_count — number of steps executed",
            "operator_remarks — free-text notes from _DBR",
            "compliance_tasks — mandatory tasks with pass/fail status (1=Completed, -1=Incomplete)",
            "incomplete_tasks — count of incomplete tasks",
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
        "purpose": "Get real-time status and runtime metrics for manufacturing equipment. NOT for OEE — use calculate_oee for that.",
        "methodology": [
            "Queries tSystem for all equipment, filtering by system_id, system_name, or area_id.",
            "Determines current status (Running/Idle) by checking for open records in tJobSystemActual (EndDateTime IS NULL = currently running).",
            "When include_tags=True, fetches live tag values from tTag (speed, counts, product codes).",
            "When include_oee=True, calculates runtime minutes and session count from tJobSystemActual — this is NOT true OEE.",
            "Use start_date and end_date (YYYY-MM-DD) for date filtering — preferred over time_window for this tool.",
        ],
        "data_sources": ["tSystem", "tJobSystemActual", "tTag"],
        "output_fields": [
            "system_id, system_name — equipment identity",
            "status — Running or Idle",
            "current_job_id — active job if running",
            "session_start — when current run started",
            "performance_metrics — total_runtime_minutes and session_count (if include_oee=True)",
            "tags — live tag values (if include_tags=True)",
        ],
        "limitations": [
            "include_oee=True returns runtime minutes only — true OEE requires calculate_oee.",
            "Live tags require tTag to be configured and connected to a real data source.",
            "time_window natural language may fail — use start_date/end_date instead.",
        ],
    },

    "calculate_oee": {
        "purpose": "Calculate industry-standard OEE (Overall Equipment Effectiveness) for a line and date range.",
        "methodology": [
            "Step 1 — Resolves line name to OeeCalculationID from tOeeCalculation (matches on Name, Key, or SystemID).",
            "Step 2 — Queries tOeeInterval for all intervals within the date range, grouped by date.",
            "Step 3 — Availability = Operating Time / Planned Production Time, where Operating = Planned − AvailabilityLossSeconds and Planned = Calendar − SystemNotScheduledSeconds.",
            "Step 4 — Performance = Actual Units / (Operating Minutes × TheoreticalRate). Clamped to 100%.",
            "Step 5 — Quality = GoodUnits / TotalUnits.",
            "Step 6 — OEE = Availability × Performance × Quality × 100.",
            "OEE data available for dates 2026-03-10 to 2026-03-12 for lines E1 (CalcID=1), E2 (CalcID=2), E3 (CalcID=3).",
        ],
        "data_sources": ["tOeeCalculation", "tOeeInterval"],
        "output_fields": [
            "period — date of the interval",
            "oee — overall OEE percentage",
            "availability — % of planned time the equipment was running",
            "performance — speed efficiency vs theoretical rate",
            "quality — ratio of good units to total units produced",
            "total_units, good_units — raw production counts",
        ],
        "limitations": [
            "Requires start_date and end_date in YYYY-MM-DD format.",
            "OEE data in this system covers 2026-03-10 to 2026-03-12 only.",
            "Known OEE values: E1=95.8/96.7/98.2%, E2=71.9/84.4/92.7%, E3=92.8/94.8/96.4% for Mar 10/11/12.",
        ],
    },

    "get_oee_downtime_events": {
        "purpose": "Show actual downtime and quality loss events for a line in a date range.",
        "methodology": [
            "Resolves line name to OeeCalculationID via tOeeCalculation.",
            "Queries tEvent filtered by the SystemID tied to that OEE configuration.",
            "Joins tEventDefinition for event category and description.",
            "Joins tEventCode for fault codes and fault names.",
            "Returns events ordered by start time descending — most recent first.",
        ],
        "data_sources": ["tEvent", "tEventDefinition", "tEventCode", "tOeeCalculation"],
        "output_fields": [
            "event_id — unique event identifier",
            "start_datetime, end_datetime — event duration",
            "impact_seconds — total seconds of production impact",
            "event_category — category from tEventDefinition",
            "fault_code, fault_name — specific fault from tEventCode",
            "notes — operator notes on the event",
        ],
        "limitations": [
            "Requires start_date and end_date — no natural language time for this tool.",
            "Only returns events where tEventDefinition.SystemID matches the OEE line config.",
            "Fault codes are optional — events without a fault code will show null.",
        ],
    },

    "get_batch_tasks": {
        "purpose": "Retrieve compliance tasks for a batch or time period with completion status.",
        "methodology": [
            "Queries tTask for all task records, joining tBatch, tSystem, and tProduct.",
            "Supports filtering by batch_id, batch_name, status (completed/incomplete/pending), and task name.",
            "When no batch_id is provided, queries across all batches (requires limit parameter).",
            "Returns a compliance rate summary (percentage of tasks completed) alongside the task list.",
            "Use status_filter='incomplete' to focus only on failures.",
        ],
        "data_sources": ["tTask", "tTaskDefinition", "tBatch", "tSystem", "tProduct"],
        "output_fields": [
            "task_id — unique task identifier",
            "task_name, task_description — what the task requires",
            "status — Completed, Incomplete, or Pending",
            "pass_fail — 1=Completed, -1=Incomplete",
            "assigned_operator — who is responsible",
            "system_name, product_name — context for the task",
        ],
        "limitations": [
            "Requires limit parameter when querying without batch_id — default limit=100.",
            "Task types in this system: Formulary, SAMPLE, Weighing Checklist.",
        ],
    },

    "analyze_task_compliance": {
        "purpose": "Analyse compliance task failure patterns across multiple batches.",
        "methodology": [
            "Groups tTask records by task name to show which task types fail most frequently.",
            "Calculates total_assignments, completed_count, incomplete_count, compliance_rate_pct per task type.",
            "Computes overall summary: total_tasks=20, total_completed=10, total_incomplete=10, overall_rate=50%, batches_covered=12.",
            "Returns a ranked list of task types by incomplete count (highest failures first).",
            "Supports filtering by system_name, product_name, and time window.",
        ],
        "data_sources": ["tTask", "tBatch", "tSystem", "tProduct"],
        "output_fields": [
            "compliance_by_task — ranked list: Formulary (10 assignments, 60%), SAMPLE (7 assignments, 42.9%), Weighing Checklist (3 assignments, 33.3%)",
            "overall_summary — total_tasks, total_completed, total_incomplete, overall_compliance_rate_pct, batches_covered",
            "top_failing_tasks — worst-performing task types",
        ],
        "limitations": [
            "Requires limit parameter — default limit=100.",
            "Results depend on the time window — narrow windows may not reflect long-term patterns.",
        ],
    },

    "get_materials": {
        "purpose": "Get RAW MATERIAL definitions from tMaterial. DO NOT use for finished products — use get_products instead.",
        "methodology": [
            "Direct SELECT from tMaterial master table with optional LEFT JOIN to tMaterialGroup.",
            "Supports filtering by material_id, material_name, material_code, material_group_id.",
            "Time filter applies to ModifiedDateTime — omit for all materials.",
            "Returns material master data only — for actual consumption use get_batch_materials.",
        ],
        "data_sources": ["tMaterial", "tMaterialGroup"],
        "output_fields": [
            "material_id, name, material_code — material identity",
            "material_group_name — group classification",
            "units — unit of measure",
            "planned_size — standard planned quantity",
        ],
        "limitations": [
            "3 distinct materials exist: Material 1 (M1), Material 3 (M3), Material 4 (M4).",
            "Material 2 code is M2 but not in active consumption records.",
            "For which products use which materials, use get_products_using_materials.",
        ],
    },

    "get_products_using_materials": {
        "purpose": "Show which FINISHED PRODUCTS have consumed each raw material in actual production.",
        "methodology": [
            "Joins tMaterialUseActual → tJob → tProduct to find product-material consumption links.",
            "Groups by material and product to show total quantity used and number of batches.",
            "Supports filtering by material_name, material_code, or time window.",
        ],
        "data_sources": ["tMaterialUseActual", "tMaterial", "tJob", "tProduct"],
        "output_fields": [
            "material_name, material_code — which raw material",
            "product_name, product_code — which finished product consumed it",
            "total_quantity_used — cumulative consumption in KGR",
            "number_of_batches — how many batches used this material",
            "last_used — most recent consumption date",
        ],
        "limitations": [
            "Only shows materials that have actual consumption records in tMaterialUseActual.",
            "All materials in this system are consumed by product P00001_FAC1_0001 only.",
        ],
    },

    "get_recipe": {
        "purpose": "Look up recipe definitions — steps, required materials, and target parameter values.",
        "methodology": [
            "Resolves recipe_name to ID via tRecipe.Name / AltName lookup.",
            "Queries tRecipe joined with tProduct and tSystem for core recipe info.",
            "Fetches step sequence from tRecipeStepDefinition (joined to tFunctionDefinition for step name).",
            "Retrieves required materials per step from tRecipeStepDefinitionMaterial joined to tMaterial.",
            "Retrieves target parameter values from tRecipeParameter joined to tParameterDefinition — includes min/max/default/data_type (no Units column in tParameterDefinition).",
            "Finds which batches used this recipe via tJobBatch.RecipeID → tJob → tBatch.",
        ],
        "data_sources": [
            "tRecipe", "tRecipeStepDefinition", "tRecipeStepDefinitionMaterial",
            "tRecipeParameter", "tParameterDefinition", "tJobBatch", "tJob", "tBatch",
            "tProduct", "tSystem"
        ],
        "output_fields": [
            "recipe_id, recipe_name, version — recipe identity",
            "product_name, product_code — which product this recipe produces",
            "steps — step sequence with planned duration and function name",
            "recipe_materials — raw materials required per step with percentage",
            "recipe_parameters — target values with min/max/default per step",
            "batches_using_recipe — recent batches that ran with this recipe (up to 10)",
        ],
        "limitations": [
            "27 recipes in the system (IDs 588–615) all for product P00001_FAC1_0001 except recipe 614 (P00001_FAC1_0002).",
            "tParameterDefinition has no Units column — use data_type and description instead.",
            "batches_using_recipe returns the 10 most recent only.",
        ],
    },

    "get_products": {
        "purpose": "Query the product master table — returns ALL products including those never produced in a batch.",
        "methodology": [
            "Direct SELECT from tProduct master table.",
            "LEFT JOIN to tJob and tBatch to calculate batch_count per product.",
            "Returns both used and unused products — unlike get_batches which only shows products that have run.",
            "Supports partial name and code matching via LIKE queries.",
        ],
        "data_sources": ["tProduct", "tJob", "tBatch"],
        "output_fields": [
            "product_id, product_name, product_code — product identity",
            "description, version, version_state — product definition details",
            "standard_size, standard_units — default planned batch size",
            "batch_count — number of batches produced for this product",
            "last_batch_date — when this product was last produced",
            "enabled — whether the product is active",
        ],
        "limitations": [
            "Two products in this system: P00001_FAC1_0001 (V1, 26 batches) and P00001_FAC1_0002 (V2, 0 batches — never produced).",
            "For full batch history per product use get_batches with product filtering.",
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
- "How are parameter deviations detected?"
- "What is the logic behind the OEE calculation?"
- "What tools are available?"
- "Explain how batch details are retrieved"
- "What is the difference between get_materials and get_products?"
- "How does the recipe tool work?"

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