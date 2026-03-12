"""
Material-related MCP tools with full explainability.
"""

import logging
from typing import TYPE_CHECKING

from src.traksys_mcp.core.exceptions import ValidationError, TrakSYSError, SecurityError
from src.traksys_mcp.models.tool_outputs import ToolResponse
from src.traksys_mcp.services import materials

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from src.traksys_mcp.services.time_resolution import TimeResolutionService


class MaterialsTools:
    def __init__(self, mcp: "FastMCP", time_service: "TimeResolutionService"):
        self.mcp = mcp
        self.time_service = time_service
        self.logger = logging.getLogger(__name__)

    def register(self) -> None:
        self._register_get_materials()
        self._register_get_products_using_materials()

    def _register_get_materials(self) -> None:
        @self.mcp.tool(
            name="get_materials",
            description="""Get material definitions and details from the TrakSYS system.

**Use when the user asks about:**
- "List all materials in the system"
- Materials by code, name, group, or type
- Planned sizes, units, etc.
"""
        )
        async def get_materials(
                material_id: int | None = None,
                material_name: str | None = None,
                material_code: str | None = None,
                material_type_id: int | None = None,
                material_group_id: int | None = None,
                time_window: str | None = None,
                start_date: str | None = None,
                end_date: str | None = None,
                limit: int = 50,
        ) -> dict:
            try:
                result = await materials.get_materials(
                    material_id=material_id, material_name=material_name, material_code=material_code,
                    material_type_id=material_type_id, material_group_id=material_group_id,
                    time_window=time_window, start_date=start_date, end_date=end_date,
                    limit=limit, time_service=self.time_service
                )
                data = result["materials"]
                if not data:
                    return ToolResponse.no_data(
                        suggestions=["No materials found", "Try removing time filter"],
                        time_info=result.get("time_info")
                    ).to_dict()

                return ToolResponse.success(
                    data={
                        "materials": data,
                        "tables_used": result.get("tables_used"),
                        "logic": result.get("logic")
                    },
                    time_info=result.get("time_info")
                ).to_dict()
            except Exception as e:
                self.logger.error("get_materials error", exc_info=True)
                return ToolResponse.error(message=str(e)).to_dict()

    def _register_get_products_using_materials(self) -> None:
        @self.mcp.tool(
            name="get_products_using_materials",
            description="""Show which products have actually used each material in real production.

**Use when the user asks:**
- "Show me which products or BOMs use each of these materials"
- "Which products use Material 4?"
"""
        )
        async def get_products_using_materials(
                material_id: int | None = None,
                material_name: str | None = None,
                material_code: str | None = None,
                time_window: str | None = None,
                start_date: str | None = None,
                end_date: str | None = None,
                limit: int = 100,
        ) -> dict:
            try:
                result = await materials.get_products_using_materials(
                    material_id=material_id, material_name=material_name, material_code=material_code,
                    time_window=time_window, start_date=start_date, end_date=end_date,
                    limit=limit, time_service=self.time_service
                )
                data = result["products"]
                if not data:
                    return ToolResponse.no_data(
                        suggestions=["No consumption recorded yet", "Check tMaterialUseActual table"],
                        time_info=result.get("time_info")
                    ).to_dict()

                return ToolResponse.success(
                    data={
                        "products": data,
                        "tables_used": result.get("tables_used"),
                        "logic": result.get("logic")
                    },
                    time_info=result.get("time_info")
                ).to_dict()
            except Exception as e:
                self.logger.error("get_products_using_materials error", exc_info=True)
                return ToolResponse.error(message=str(e)).to_dict()