"""
Batch-related MCP tools.

Class-based composition - each tool domain is a separate class
that registers its tools with the FastMCP instance.
"""

import logging
from typing import TYPE_CHECKING

from src.traksys_mcp.core.exceptions import ValidationError, TrakSYSError, SecurityError

from src.traksys_mcp.models.tool_outputs import ToolResponse
from src.traksys_mcp.services import batches

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from src.traksys_mcp.services.time_resolution import TimeResolutionService, logger


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
        self._register_get_batch_quality()

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
                batch_id: int | None = None,
                batch_name: str | None = None,
                system_id: int | None = None,
                job_id: int | None = None,
                time_window: str | None = None,
                start_date: str | None = None,
                end_date: str | None = None,
                state: int | None = None,
                limit: int = 50,
        ) -> dict:
            try:
                result = await batches.get_batches(
                    batch_id=batch_id,
                    batch_name=batch_name,
                    system_id=system_id,
                    job_id=job_id,
                    time_window=time_window,
                    start_date=start_date,
                    end_date=end_date,
                    state=state,
                    limit=limit,
                    time_service=self.time_service,
                )
                batch_list = result["batches"]
                time_info = result.get("time_info")

                if not batch_list:
                    return ToolResponse.no_data(
                        suggestions=[
                            "No batches found for this period",
                            "Try a broader time window",
                            "Verify system_id or batch_id is correct",
                        ],
                        time_info=time_info,
                    ).to_dict()

                if time_info and time_info.get("fallback_triggered"):
                    return ToolResponse.partial(
                        data=batch_list,
                        time_info=time_info,
                        message=time_info.get("message"),
                    ).to_dict()

                return ToolResponse.success(
                    data=batch_list,
                    time_info=time_info,
                ).to_dict()

            except SecurityError as e:
                return ToolResponse.error(
                    message=f"Query blocked: {e}",
                ).to_dict()
            except TrakSYSError as e:
                self.logger.error("get_batches error: %s", e, exc_info=True)
                return ToolResponse.error(message=str(e)).to_dict()
            except Exception as e:
                self.logger.error("get_batches unexpected error: %s", e, exc_info=True)
                return ToolResponse.error(
                    message=str(e),
                    suggestions=[
                        "Verify system_id or batch_id is correct",
                        "Try 'last 7 days' or a specific date range",
                        "Check database connection",
                    ],
                ).to_dict()

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
        async def get_batch_parameters(
                batch_id: int | None = None,
                batch_name: str | None = None,
                parameter_names: list[str] | None = None,
                deviation_only: bool = False,
                time_window: str | None = None,
                start_date: str | None = None,
                end_date: str | None = None,
                limit: int = 100,
        ) -> dict:
            try:
                result = await batches.get_batch_parameters(
                    batch_id=batch_id,
                    batch_name=batch_name,
                    parameter_names=parameter_names,
                    deviation_only=deviation_only,
                    time_window=time_window,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                    time_service=self.time_service,
                )
                param_list = result["parameters"]
                time_info = result.get("time_info")

                if not param_list:
                    return ToolResponse.no_data(
                        suggestions=[
                            "No parameters found for this batch",
                            "Verify batch_id or batch_name is correct",
                            "Try deviation_only=false to see all parameters",
                        ],
                        time_info=time_info,
                    ).to_dict()

                if time_info and time_info.get("fallback_triggered"):
                    return ToolResponse.partial(
                        data=param_list,
                        time_info=time_info,
                        message=time_info.get("message"),
                    ).to_dict()

                return ToolResponse.success(
                    data=param_list,
                    time_info=time_info,
                ).to_dict()

            except SecurityError as e:
                return ToolResponse.error(message=f"Query blocked: {e}").to_dict()
            except TrakSYSError as e:
                self.logger.error("get_batch_parameters error: %s", e, exc_info=True)
                return ToolResponse.error(message=str(e)).to_dict()
            except Exception as e:
                self.logger.error("get_batch_parameters unexpected error: %s", e, exc_info=True)
                return ToolResponse.error(
                    message="Unexpected error occurred",
                    suggestions=[
                        "Verify batch_id or batch_name exists",
                        "Try deviation_only=true to filter deviations only",
                        "Check database connection",
                    ],
                ).to_dict()

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
        async def get_batch_materials(
                batch_id: int | None = None,
                batch_name: str | None = None,
                job_id: int | None = None,
                material_names: list[str] | None = None,
                material_codes: list[str] | None = None,
                time_window: str | None = None,
                start_date: str | None = None,
                end_date: str | None = None,
                limit: int = 100,
        ) -> dict:
            try:
                result = await batches.get_batch_materials(
                    batch_id=batch_id,
                    batch_name=batch_name,
                    job_id=job_id,
                    material_names=material_names,
                    material_codes=material_codes,
                    time_window=time_window,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                    time_service=self.time_service,
                )
                mat_list = result["materials"]
                time_info = result.get("time_info")

                if not mat_list:
                    return ToolResponse.no_data(
                        suggestions=[
                            "No materials found for this batch",
                            "Verify batch_id or batch_name is correct",
                            "Check tMaterialUseActual is populated",
                        ],
                        time_info=time_info,
                    ).to_dict()

                if time_info and time_info.get("fallback_triggered"):
                    return ToolResponse.partial(
                        data=mat_list,
                        time_info=time_info,
                        message=time_info.get("message"),
                    ).to_dict()

                return ToolResponse.success(
                    data=mat_list,
                    time_info=time_info,
                ).to_dict()

            except SecurityError as e:
                return ToolResponse.error(message=f"Query blocked: {e}").to_dict()
            except TrakSYSError as e:
                self.logger.error("get_batch_materials error: %s", e, exc_info=True)
                return ToolResponse.error(message=str(e)).to_dict()
            except Exception as e:
                self.logger.error("get_batch_materials unexpected error: %s", e, exc_info=True)
                return ToolResponse.error(
                    message="Unexpected error occurred",
                    suggestions=[
                        "Verify batch_id or batch_name exists",
                        "Check material name or code spelling",
                        "Check database connection",
                    ],
                ).to_dict()

    def _register_get_batch_quality(self) -> None:
            """Register the get_batch_quality tool."""

            @self.mcp.tool(
                name="get_batch_quality",
                description="""Get quality loss events for batches — quantities rejected, root cause categories, and category groups.

        Use this tool when the user asks about:
        - Which batches had quality losses or rejects in a time period (Q7)
        - Root causes of quality rejects for a specific product (Q8)
        - Quality loss quantities per batch or production line
        - Most common reject categories this week/month/quarter

        Supports natural language time: 'last 10 days', 'this quarter', 'yesterday'.
        Falls back to nearest available data if requested dates have no records.

        For process parameter deviations (temperature, pressure, speed) use get_batch_parameters instead.
        """,
            )
            async def get_batch_quality(
                    batch_id: int | None = None,
                    product_name: str | None = None,
                    system_id: int | None = None,
                    time_window: str | None = None,
                    start_date: str | None = None,
                    end_date: str | None = None,
                    category_filter: list[str] | None = None,
                    limit: int = 50,
            ) -> dict:
                try:
                    result = await batches.get_batch_quality(
                        batch_id=batch_id,
                        product_name=product_name,
                        system_id=system_id,
                        time_window=time_window,
                        start_date=start_date,
                        end_date=end_date,
                        category_filter=category_filter,
                        limit=limit,
                        time_service=self.time_service,
                    )

                    events = result["quality_events"]
                    time_info = result.get("time_info")

                    if not events:
                        return ToolResponse.no_data(
                            suggestions=[
                                "No quality loss records found for this period",
                                "Try a broader time window",
                                "Verify product_name or category_filter spelling",
                                "Quality loss data may not yet be recorded for these batches",
                            ],
                            time_info=time_info,
                        ).to_dict()

                    if time_info and time_info.get("fallback_triggered"):
                        return ToolResponse.partial(
                            data=events,
                            time_info=time_info,
                            message=time_info.get("message"),
                        ).to_dict()

                    return ToolResponse.success(
                        data=events,
                        time_info=time_info,
                    ).to_dict()

                except SecurityError as e:
                    return ToolResponse.error(
                        message=f"Query blocked: {e}",
                        suggestions=["Check input parameters for invalid characters"],
                    ).to_dict()
                except ValidationError as e:
                    return ToolResponse.error(
                        message=f"Invalid input: {e}",
                        suggestions=["Verify batch_id is an integer, limit is between 1-500"],
                    ).to_dict()
                except TrakSYSError as e:
                    logger.error("get_batch_quality error: %s", e, exc_info=True)
                    return ToolResponse.error(
                        message=str(e),
                    ).to_dict()
                except Exception as e:
                    logger.error("get_batch_quality unexpected error: %s", e, exc_info=True)
                    return ToolResponse.error(
                        message="Unexpected error occurred",
                        suggestions=[
                            "Verify batch_id or system_id is correct",
                            "Try a specific date range instead of time_window",
                            "For parameter deviations use get_batch_parameters instead",
                        ],
                    ).to_dict()


