"""
Batch-related MCP tools.

Class-based composition - each tool domain is a separate class
that registers its tools with the FastMCP instance.
"""

import logging
from typing import TYPE_CHECKING, Optional


from traksys_mcp.models.responses import ToolResponse
from traksys_mcp.services import batches

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from traksys_mcp.services.time_resolution import TimeResolutionService


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
        # Add more batch-related tools here as they're built:
        # self._register_get_batch_by_id()
        # self._register_get_batches_for_job()

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
            """Get batches from TrakSYS."""
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
                        "Try 'last 7 days' or a specific date range like '2024-08-25' to '2024-08-31'",
                        "Check database connection",
                        "Verify that tBatch, tJob, tProduct, tSystem tables are accessible"
                    ]
                )
                return response.to_dict()