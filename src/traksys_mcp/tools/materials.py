"""
Material-related MCP tools with full explainability.
"""

import logging
from typing import TYPE_CHECKING

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
            description="""Get RAW MATERIAL definitions from the tMaterial table (ingredients, components, BOM items).

**Use ONLY when the user asks about raw materials or ingredients:**
- "List all raw materials in the system"
- "What is material code M3?"
- "Show me materials in the BOM Raw Materials group"
- "What ingredients do we use?"
- "Show me material M1 details"

**DO NOT use this tool for finished products.**
For finished products (e.g. P00001_FAC1_0001), use `get_batches` — every batch
response includes product_name and product_code from tProduct.

**Key Parameters:**
- `material_name`: Filter by name (e.g. 'Material 1')
- `material_code`: Filter by code (e.g. 'M1', 'M3')
- `material_group_id`: Filter by group (e.g. BOM Raw Materials group)
- `limit`: Maximum records to return (default 50)
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
                    material_id=material_id, material_name=material_name,
                    material_code=material_code, material_type_id=material_type_id,
                    material_group_id=material_group_id, time_window=time_window,
                    start_date=start_date, end_date=end_date,
                    limit=limit, time_service=self.time_service
                )
                data = result["materials"]
                if not data:
                    return ToolResponse.no_data(
                        suggestions=[
                            "No materials found matching the filter",
                            "Try removing material_name or material_code filters",
                            "Check tMaterial table is populated",
                        ],
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
            description="""Show which FINISHED PRODUCTS have actually consumed each raw material in real production.

**Use when the user asks:**
- "Which products use Material 4?"
- "What finished products consume M3?"
- "Show me which products or BOMs use each of these materials"
- "Which product lines use the most Material 1?"

**This tool links raw materials → finished products via actual consumption records.**
It queries tMaterialUseActual joined through tJob → tBatch → tProduct.

**DO NOT confuse with get_materials** — that tool lists raw material definitions.
This tool shows which finished products (tProduct) consumed those raw materials.

**Key Parameters:**
- `material_name`: Filter to a specific raw material (e.g. 'Material 3')
- `material_code`: Filter by code (e.g. 'M3')
- `time_window`: Limit to a time period (e.g. 'last 30 days')
- `limit`: Maximum records to return (default 100)
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
                    material_id=material_id, material_name=material_name,
                    material_code=material_code, time_window=time_window,
                    start_date=start_date, end_date=end_date,
                    limit=limit, time_service=self.time_service
                )
                data = result["products"]
                if not data:
                    return ToolResponse.no_data(
                        suggestions=[
                            "No consumption recorded yet for this material",
                            "Check tMaterialUseActual table has records",
                            "Try without material filter to see all product-material links",
                        ],
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