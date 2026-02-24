"""
Batch-related MCP tools.

Class-based composition - each tool domain is a separate class
that registers its tools with the FastMCP instance.
"""

import logging
from typing import TYPE_CHECKING, Optional, List

from src.traksys_mcp.models.responses import ToolResponse
from src.traksys_mcp.services import batches
from src.traksys_mcp.models.tool_inputs import GetBatchesInput, GetBatchParametersInput, GetBatchMaterialsInput

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from src.traksys_mcp.services.time_resolution import TimeResolutionService


class BatchTools:
    """
    Batch tool collection.

    Encapsulates all batch-related MCP tools and their logic.
    Uses dependency injection for services.
    """

    def __init__(self, mcp: "FastMCP", time_service: "TimeResolutionService"):
        """
        Initialize batch tools.

        Args:
            mcp: FastMCP instance to register tools with
            time_service: TimeResolutionService for date handling
        """
        self.mcp = mcp
        self.time_service = time_service
        self.logger = logging.getLogger(__name__)

    def register(self) -> None:
        """Register all batch tools with the MCP server."""
        self._register_get_batches()
        self._register_get_batch_parameters()
        self._register_get_batch_materials()

    def _register_get_batches(self) -> None:
        """Register the get_batches tool."""

        @self.mcp.tool(
            name="get_batches",
            description="""Get batch information from the TrakSYS manufacturing system.

**Use this tool when the user asks about:**
- Production orders or batches on a specific line/system
- Batch details by ID
- Batches within a date range
- Recent production runs
- Batch quantities, timing, and status

**Intelligent time handling:**
The tool supports natural language time expressions like "yesterday" or
"last 7 days". If the requested dates don't exist in the database, the
system automatically falls back to the nearest available data and explains
what happened.

**Returns:**
- Batch ID, name, system/line, job info, product details
- Start/end times, planned vs actual quantities
- State/status information
- If time fallback occurred, includes explanation message

**Examples:**
- "Show me batches from yesterday" → falls back to most recent data
- "Get batches for System ID 5 in last 7 days"
- "Find batch ID 1234"
"""
        )
        async def get_batches(arguments: GetBatchesInput) -> dict:
            """Get batches from TrakSYS."""
            try:
                # Use model_dump() to convert the validated Pydantic model into a dictionary
                result = await batches.get_batches(
                    time_service=self.time_service,
                    **arguments.model_dump()
                )

                batch_list = result["batches"]
                time_info = result.get("time_info")

                if time_info and time_info.get("fallback_triggered"):
                    response = ToolResponse.partial(
                        data=batch_list,
                        time_info=time_info,
                        message=time_info.get("message")
                    )
                else:
                    response = ToolResponse.success(
                        data=batch_list,
                        time_info=time_info
                    )

                return response.to_dict()

            except Exception as e:
                self.logger.error(f"get_batches failed: {e}", exc_info=True)
                response = ToolResponse.error(
                    error=str(e),
                    suggestions=[
                        "Verify the system_id or batch_id is correct",
                        "Try 'last 7 days' or a specific date range like '2024-08-25' to '2024-08-31'",
                        "Check database connection",
                        "Verify that tBatch, tJob, tProduct, tSystem tables are accessible"
                    ]
                )
                return response.to_dict()

    def _register_get_batch_parameters(self) -> None:
        """Register the get_batch_parameters tool."""

        @self.mcp.tool(
            name="get_batch_parameters",
            description="""Get process parameters (temperature, pressure, speed, etc.) for one or more batches.

**Use when the user asks about:**
- Parameter values & deviations for a specific batch
- All deviations in a time period (Q2)
- Performance component data (Q6)
- "Show me temperature & pressure for Batch AA001"
- "Were there any deviations yesterday?"

**Important usage notes:**
- If the user gives a batch **name or code** (e.g. 'AA001') → use `batch_name`
- If the user gives a **numeric ID** (e.g. 456) → use `batch_id`

**Intelligent time handling:**
Supports natural language + automatic fallback to available data.

**Deviation detection:**
Uses tParameterDefinition.MinimumValue / MaximumValue.

**Primary tables:** tBatchParameter, tBatch, tParameterDefinition
"""
        )
        async def get_batch_parameters(arguments: GetBatchParametersInput) -> dict:
            """Get batch parameters from TrakSYS."""
            try:
                result = await batches.get_batch_parameters(
                    time_service=self.time_service,
                    **arguments.model_dump()
                )

                param_list = result["parameters"]
                time_info = result.get("time_info")

                if time_info and time_info.get("fallback_triggered"):
                    response = ToolResponse.partial(
                        data=param_list,
                        time_info=time_info,
                        message=time_info.get("message")
                    )
                else:
                    response = ToolResponse.success(
                        data=param_list,
                        time_info=time_info
                    )

                return response.to_dict()

            except Exception as e:
                self.logger.error(f"get_batch_parameters failed: {e}", exc_info=True)
                response = ToolResponse.error(
                    error=str(e),
                    suggestions=[
                        "Verify the batch_id or batch_name exists",
                        "Try 'yesterday' or 'last 7 days'",
                        "Use deviation_only=true to see only out-of-range values",
                        "Check tBatchParameter, tParameterDefinition tables"
                    ]
                )
                return response.to_dict()

    def _register_get_batch_materials(self) -> None:
        """Register the get_batch_materials tool."""

        @self.mcp.tool(
            name="get_batch_materials",
            description="""Get actual material consumption / usage for batches.

**Use when asked about:**
- Materials used in a specific batch
- Raw material consumption over time
- "What materials were used in batch XYZ?"
- "Show material usage last week"
- Over/under consumption compared to planned

**Important usage notes:**
- If the user gives a batch **name or code** (e.g. 'AA001') → use `batch_name`
- If the user gives a **numeric ID** (e.g. 456) → use `batch_id`

**Intelligent time handling:**
Supports natural language time expressions with automatic fallback.
Can filter by material name or code.

**Primary tables:** tMaterialUseActual, tBatch, tMaterial
"""
        )
        async def get_batch_materials(arguments: GetBatchMaterialsInput) -> dict:
            """Get batch material usage from TrakSYS."""
            try:
                result = await batches.get_batch_materials(
                    time_service=self.time_service,
                    **arguments.model_dump()
                )

                mat_list = result["materials"]
                time_info = result.get("time_info")

                if time_info and time_info.get("fallback_triggered"):
                    response = ToolResponse.partial(
                        data=mat_list,
                        time_info=time_info,
                        message=time_info.get("message")
                    )
                else:
                    response = ToolResponse.success(
                        data=mat_list,
                        time_info=time_info
                    )

                return response.to_dict()

            except Exception as e:
                self.logger.error(f"get_batch_materials failed: {e}", exc_info=True)
                response = ToolResponse.error(
                    error=str(e),
                    suggestions=[
                        "Verify the batch_id or batch_name exists",
                        "Try 'yesterday' or 'last 7 days'",
                        "Check material name / code spelling",
                        "Confirm tMaterialUseActual and tMaterial tables are populated"
                    ]
                )
                return response.to_dict()