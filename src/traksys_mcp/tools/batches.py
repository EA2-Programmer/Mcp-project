"""
Batch-related MCP tools.

Class-based composition - each tool domain is a separate class
that registers its tools with the FastMCP instance.
"""

import logging
from typing import TYPE_CHECKING, Optional, List

from src.traksys_mcp.models.responses import ToolResponse
from src.traksys_mcp.services import batches

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from src.traksys_mcp.services.time_resolution import TimeResolutionService


class BatchTools:
    """
    Batch tool collection.
    """

    def __init__(self, mcp: "FastMCP", time_service: "TimeResolutionService"):
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
    """
        )
        async def get_batches(
                batch_id: Optional[int] = None,
                system_id: Optional[int] = None,
                job_id: Optional[int] = None,
                time_window: Optional[str] = None,
                start_date: Optional[str] = None,
                end_date: Optional[str] = None,
                state: Optional[int] = None,
                limit: int = 50
        ) -> dict:
            try:
                result = await batches.get_batches(
                    batch_id=batch_id,
                    system_id=system_id,
                    job_id=job_id,
                    time_window=time_window,
                    start_date=start_date,
                    end_date=end_date,
                    state=state,
                    limit=limit,
                    time_service=self.time_service
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
                        "Try 'last 7 days' or a specific date range",
                        "Check database connection"
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
    - "Show me temperature & pressure for Batch AA001"
    - "Were there any deviations yesterday?"

    **Intelligent time handling:**
    Supports natural language + automatic fallback.

    **Deviation detection:**
    Uses tParameterDefinition.MinimumValue / MaximumValue.
    """
        )
        async def get_batch_parameters(
                batch_id: Optional[int] = None,
                parameter_names: Optional[List[str]] = None,
                deviation_only: bool = False,
                time_window: Optional[str] = None,
                start_date: Optional[str] = None,
                end_date: Optional[str] = None,
                limit: int = 100
        ) -> dict:
            """Get batch parameters from TrakSYS."""
            try:
                result = await batches.get_batch_parameters(
                    batch_id=batch_id,
                    parameter_names=parameter_names,
                    deviation_only=deviation_only,
                    time_window=time_window,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                    time_service=self.time_service
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
                        "Try 'yesterday' or 'last 7 days'",
                        "Use deviation_only=true to see only out-of-range values",
                        "Check tBatchParameter table has data"
                    ]
                )
                return response.to_dict()

    def _register_get_batch_materials(self) -> None:
        """Register the get_batch_materials tool."""

        @self.mcp.tool(
            name="get_batch_materials",
            description="""Get actual material consumption / usage for batches.

    Use when asked about:
    • Materials used in a specific batch
    • Raw material consumption over time
    • "What materials were used in batch XYZ?"
    • "Show material usage last week"
    """
        )
        async def get_batch_materials(
                batch_id: Optional[int] = None,
                material_names: Optional[List[str]] = None,
                material_codes: Optional[List[str]] = None,
                time_window: Optional[str] = None,
                start_date: Optional[str] = None,
                end_date: Optional[str] = None,
                limit: int = 100
        ) -> dict:
            try:
                result = await batches.get_batch_materials(
                    batch_id=batch_id,
                    material_names=material_names,
                    material_codes=material_codes,
                    time_window=time_window,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                    time_service=self.time_service
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
                        "Try 'yesterday' or 'last 7 days'",
                        "Check material name / code spelling"
                    ]
                )
                return response.to_dict()