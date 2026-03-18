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
    from src.traksys_mcp.services.langfuse_tracing import TracingService

class PerformanceTools:
    """
    Tools for checking live equipment status on the factory floor.
    """

    def __init__(
        self,
        mcp: "FastMCP",
        tracing: "TracingService",
    ):
        self.mcp = mcp
        self.tracing = tracing
        self.logger = logging.getLogger(__name__)

    def register(self) -> None:
        self._register_get_equipment_state()

    def _register_get_equipment_state(self) -> None:

        @self.mcp.tool(
            name="get_equipment_state",
            description="""Get the LIVE, real-time status of manufacturing equipment.

**Use this tool when the user asks:**
- "What is running on the Packaging Line right now?"
- "Are there any active faults on the Labeler?"
- "List all active machines in Area 2."
- "Is Machine E1 currently running a job?"

**DO NOT use this tool for historical data or OEE.** If the user asks "How did we do yesterday?" or "What was the OEE?", use `calculate_oee`.

**Key Parameters:**
- `system_name`: Equipment name (e.g., 'Line E1').
- `area_id`: To see all machines in a physical zone.
- `include_active_faults`: Set to True to check if the machine is currently broken/stopped.
"""
        )
        async def get_equipment_state(params: GetEquipmentStateInput) -> dict:
            inputs = params.model_dump()
            async with self.tracing.trace_tool("get_equipment_state", inputs) as span:
                try:
                    result = await performance.get_equipment_state(
                        trace_span=span,
                        **inputs,
                    )

                    equipment_list = result["equipment"]

                    if not equipment_list:
                        return ToolResponse.no_data(
                            suggestions=[
                                "Verify the system_name or system_id is correct",
                                "Ensure the equipment is enabled (IsTemplate=0) in tSystem",
                            ]
                        ).to_dict()

                    return ToolResponse.success(data=equipment_list).to_dict()

                except Exception as e:
                    self.tracing.record_error(span, e, "get_equipment_state")
                    self.logger.error("get_equipment_state failed: %s", e, exc_info=True)
                    return ToolResponse.error(
                        message=str(e),
                        suggestions=["Verify the system_name or system_id is correct"]
                    ).to_dict()