import logging
from typing import TYPE_CHECKING
from src.traksys_mcp.models.tool_outputs import ToolResponse
# Import the service function you fixed earlier
from src.traksys_mcp.services.analysis import calculate_oee as oee_service
from src.traksys_mcp.core.exceptions import ValidationError, SecurityError

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from src.traksys_mcp.services.time_resolution import TimeResolutionService

class AnalysisTools:
    """Encapsulates OEE and analysis tools."""

    def __init__(self, mcp: "FastMCP", time_service: "TimeResolutionService"):
        self.mcp = mcp
        self.time_service = time_service
        self.logger = logging.getLogger(__name__)

    def register(self) -> None:
        """Register all analysis tools."""
        self._register_calculate_oee()

    def _register_calculate_oee(self) -> None:
        @self.mcp.tool(
            name="calculate_oee",
            description="Calculate OEE or proxy metrics. Requires start_date and end_date (YYYY-MM-DD)."
        )
        async def calculate_oee(
                line: str | None = None,
                start_date: str | None = None,
                end_date: str | None = None,
                granularity: str = "daily",
                breakdown: bool = True,
        ) -> dict:
            try:
                # Validation and service call logic here...
                result = await oee_service(
                    line=line,
                    start_date=start_date,
                    end_date=end_date,
                    granularity=granularity,
                    breakdown=breakdown,
                    time_service=self.time_service,
                )
                return ToolResponse.success(data=result.get("oee")).to_dict()
            except Exception as e:
                self.logger.error("calculate_oee error: %s", e)
                return ToolResponse.error(message=str(e)).to_dict()