"""
Performance and Equipment-related MCP tools.
"""

import logging
from typing import TYPE_CHECKING

from src.traksys_mcp.models.tool_outputs import ToolResponse
from src.traksys_mcp.services import performance
from src.traksys_mcp.models.tool_inputs import GetEquipmentStateInput

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from src.traksys_mcp.services.time_resolution import TimeResolutionService
    from src.traksys_mcp.services.langfuse_tracing import TracingService


class PerformanceTools:
    """
    Tools for checking equipment status and production performance.

    Lets you ask questions about:
    - Is a machine running right now?
    - How many sessions did equipment run last week?
    - What's the current production count?

    For true OEE (Availability × Performance × Quality), use AnalysisTools.calculate_oee.
    """

    def __init__(
        self,
        mcp: "FastMCP",
        time_service: "TimeResolutionService",
        tracing: "TracingService",
    ):
        self.mcp = mcp
        self.time_service = time_service
        self.tracing = tracing
        self.logger = logging.getLogger(__name__)

    def register(self) -> None:
        """Register all performance tools."""
        self._register_get_equipment_state()

    def _register_get_equipment_state(self) -> None:

        @self.mcp.tool(
            name="get_equipment_state",
            description="""Get real-time status and runtime metrics for manufacturing equipment.

**Use this tool when the user asks about:**
- "What is the current status of Line E1?"
- "Which machines are currently idle?"
- "Show me live tag values for E1."
- "How many shifts did E2 run last week?"

**DO NOT use this tool for OEE questions.**
For OEE (Overall Equipment Effectiveness), Availability %, Performance %, or Quality %,
use `calculate_oee` instead — it reads from tOeeCalculation and tOeeInterval for
mathematically correct results.

**Key Parameters:**
- `system_name`: Equipment name (e.g., 'E1', 'Packer 01').
- `include_tags`: Set to true for live counts, speeds, and product codes from tTag.
- `include_oee`: Set to true for runtime minutes and session counts (this is NOT true OEE).
- `start_date` / `end_date`: Use YYYY-MM-DD format for date filtering (preferred over time_window).
"""
        )
        async def get_equipment_state(params: GetEquipmentStateInput) -> dict:
            inputs = params.model_dump()
            async with self.tracing.trace_tool("get_equipment_state", inputs) as span:
                try:
                    result = await performance.get_equipment_state(
                        time_service=self.time_service,
                        trace_span=span,
                        **inputs,
                    )

                    equipment_list = result["equipment"]
                    time_info      = result.get("time_info")

                    if not equipment_list:
                        response = ToolResponse.no_data(
                            suggestions=[
                                "Verify the system_name or system_id is correct",
                                "Ensure the equipment is enabled in tSystem",
                                "Try a broader area_id or time_window",
                            ],
                            time_info=time_info,
                        )
                    elif time_info and time_info.get("fallback_triggered"):
                        response = ToolResponse.partial(
                            data=equipment_list,
                            time_info=time_info,
                            message=time_info.get("message"),
                        )
                    else:
                        response = ToolResponse.success(
                            data=equipment_list,
                            time_info=time_info,
                        )

                    self.tracing.set_output(span, response.to_dict())
                    return response.to_dict()

                except Exception as e:
                    self.tracing.record_error(span, e, "get_equipment_state")
                    self.logger.error("get_equipment_state failed: %s", e, exc_info=True)
                    return ToolResponse.error(
                        message=str(e),
                        suggestions=[
                            "Verify the system_name or system_id is correct",
                            "Check if the equipment is Enabled in tSystem",
                            "Try start_date and end_date in YYYY-MM-DD format",
                            "Ensure tTag and tJobSystemActual tables are accessible",
                        ]
                    ).to_dict()