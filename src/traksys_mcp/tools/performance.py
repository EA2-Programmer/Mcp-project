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


class PerformanceTools:
    """
    Performance tool collection.

    Encapsulates all equipment and OEE related tools.
    """

    def __init__(self, mcp: "FastMCP", time_service: "TimeResolutionService"):
        self.mcp = mcp
        self.time_service = time_service
        self.logger = logging.getLogger(__name__)

    def register(self) -> None:
        """Register all performance tools."""
        self._register_get_equipment_state()

    def _register_get_equipment_state(self) -> None:
        """Register the get_equipment_state tool."""

        @self.mcp.tool(
            name="get_equipment_state",
            description="""Get real-time status, downtime, and performance metrics for manufacturing equipment.

**Use this tool when the user asks about:**
- "What is the status of Packer 01?"
- "Which machines are currently idle?"
- "Show me OEE for the filling line yesterday."
- "What are the live tag values for the Boiler?"
- "How much downtime did Area 5 have last week?"

**Intelligent Features:**
- **Live Status**: Shows if a machine is 'Running' or 'Idle' based on open production sessions.
- **Real-time Tags**: Can fetch live counts, product codes, and speeds directly from tTag.
- **OEE & Availability**: Calculates runtime and session counts over any natural language time period (e.g., 'yesterday').
- **Smart Fallback**: If requested dates have no data, it automatically finds the most recent available data.

**Key Parameters:**
- `system_name`: Human name of the machine (e.g., 'Packer 01').
- `include_tags`: Set to true for live speeds/counts.
- `include_oee`: Set to true for downtime/availability analysis.
"""
        )
        async def get_equipment_state(arguments: GetEquipmentStateInput) -> dict:
            try:
                result = await performance.get_equipment_state(
                    time_service=self.time_service,
                    **arguments.model_dump()
                )

                equipment_list = result["equipment"]
                time_info = result.get("time_info")

                if not equipment_list:
                    return ToolResponse.no_data(
                        suggestions=[
                            "Verify the system_name or system_id is correct",
                            "Ensure the equipment is enabled in tSystem",
                            "Try a broader area_id or time_window",
                        ],
                        time_info=time_info,
                    ).to_dict()

                if time_info and time_info.get("fallback_triggered"):
                    response = ToolResponse.partial(
                        data=equipment_list,
                        time_info=time_info,
                        message=time_info.get("message")
                    )
                else:
                    response = ToolResponse.success(
                        data=equipment_list,
                        time_info=time_info
                    )

                return response.to_dict()

            except Exception as e:
                self.logger.error(f"get_equipment_state failed: {e}", exc_info=True)
                return ToolResponse.error(
                    message=str(e),
                    suggestions=[
                        "Verify the system_name or system_id is correct",
                        "Check if the equipment is Enabled in tSystem",
                        "Try 'last 7 days' to see historical performance",
                        "Ensure tTag and tJobSystemActual tables are accessible"
                    ]
                ).to_dict()
