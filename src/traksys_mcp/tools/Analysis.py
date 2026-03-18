"""
OEE & Analysis tools with explainability.
"""

import logging
from typing import TYPE_CHECKING

from src.traksys_mcp.core.exceptions import ValidationError, TrakSYSError, SecurityError
from src.traksys_mcp.models.tool_outputs import ToolResponse
from src.traksys_mcp.services import analysis   # ← your new service

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from src.traksys_mcp.services.time_resolution import TimeResolutionService


class AnalysisTools:
    def __init__(self, mcp: "FastMCP", time_service: "TimeResolutionService"):
        self.mcp = mcp
        self.time_service = time_service
        self.logger = logging.getLogger(__name__)

    def register(self) -> None:
        self._register_calculate_oee()
        self._register_get_oee_downtime_events()

    def _register_calculate_oee(self) -> None:
        @self.mcp.tool(
            name="calculate_oee",
            description="""Calculate Overall Equipment Effectiveness (OEE) for a line and date range.

**Use when asked about:**
- OEE Calculation
- OEE this week vs last week
- Availability / Performance / Quality breakdown
- Line performance KPIs

**Requires:** start_date and end_date (YYYY-MM-DD)
**Returns:** OEE % + full breakdown when requested.
"""
        )
        async def calculate_oee(
            line: str | None = None,
            start_date: str | None = None,
            end_date: str | None = None,
            granularity: str = "daily",
            breakdown: bool = True,
        ) -> dict:
            try:
                result = await analysis.calculate_oee(
                    line=line,
                    start_date=start_date,
                    end_date=end_date,
                    granularity=granularity,
                    breakdown=breakdown,
                    time_service=self.time_service,
                )
                data = result.get("oee")

                if not data:
                    return ToolResponse.no_data(
                        suggestions=["No OEE intervals found in this period", "Check tOeeInterval table"],
                        time_info=result.get("time_info")
                    ).to_dict()

                return ToolResponse.success(
                    data={
                        "oee": data,
                        "tables_used": result.get("tables_used"),
                        "logic": result.get("logic")
                    },
                    time_info=result.get("time_info")
                ).to_dict()

            except Exception as e:
                self.logger.error("calculate_oee error", exc_info=True)
                return ToolResponse.error(message=str(e)).to_dict()

    def _register_get_oee_downtime_events(self) -> None:
        @self.mcp.tool(
            name="get_oee_downtime_events",
            description="""Show actual downtime and quality events for a line in a date range.

**Use when the user asks:**
- "Why was quality low on Line E1?"
- "Show me the events that caused downtime yesterday"
- "What events hurt availability today?"

Returns: event name, duration, impact, notes.
"""
        )
        async def get_oee_downtime_events(
            line: str | None = None,
            start_date: str | None = None,
            end_date: str | None = None,
            limit: int = 50,
        ) -> dict:
            try:
                result = await analysis.get_oee_downtime_events(
                    line=line,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                    time_service=self.time_service,
                )
                data = result.get("events")

                if not data:
                    return ToolResponse.no_data(
                        suggestions=["No events recorded in this period", "Check tEvent table"],
                        time_info=result.get("time_info")
                    ).to_dict()

                return ToolResponse.success(
                    data={
                        "events": data,
                        "tables_used": result.get("tables_used"),
                        "logic": result.get("logic")
                    },
                    time_info=result.get("time_info")
                ).to_dict()

            except Exception as e:
                self.logger.error("get_oee_downtime_events error", exc_info=True)
                return ToolResponse.error(message=str(e)).to_dict()