"""
Recipe and Product MCP tools.
"""

import logging
from typing import TYPE_CHECKING

from src.traksys_mcp.models.tool_inputs import GetRecipeInput, GetProductsInput
from src.traksys_mcp.models.tool_outputs import ToolResponse
from src.traksys_mcp.services import product as product_service  # ← the fix

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from src.traksys_mcp.services.langfuse_tracing import TracingService


class RecipeTools:
    """Recipe lookup and product master tools."""

    def __init__(self, mcp: "FastMCP", tracing: "TracingService"):
        self.mcp = mcp
        self.tracing = tracing
        self.logger = logging.getLogger(__name__)

    def register(self) -> None:
        self._register_get_recipe()
        self._register_get_products()

    def _register_get_recipe(self) -> None:
        @self.mcp.tool(
            name="get_recipe",
            description="""Look up recipe definitions including steps, required materials, and target parameters.

**Use this tool when the user asks about:**
- "What is recipe ID 595?"
- "Where was recipe MBR2_0100_A1 used?"
- "What steps does the Chocolate PoC New recipe have?"
- "What materials does recipe 612 require?"
- "Which batches used this recipe?"
- "What are the target parameter values for recipe MBR1_0100_A1?"
- "What recipe was used for product P00001_FAC1_0001?"
- "What is the planned duration for recipe 589?"

**Recipe → Batch connection:**
Every batch response includes a `recipe_id`. Use that to look up the full recipe definition.
Chain: tRecipe → tJobBatch.RecipeID → tJob → tBatch

**Returns per recipe:**
- `steps`: Step sequence from tRecipeStepDefinition
- `recipe_materials`: Raw materials required per step (tRecipeStepDefinitionMaterial)
- `recipe_parameters`: Target values with min/max bounds per step (tRecipeParameter → tParameterDefinition)
- `batches_using_recipe`: Batches produced using this recipe

**Key Parameters:**
- `recipe_id`: Direct lookup by ID (e.g. 595, 612)
- `recipe_name`: Lookup by name (e.g. 'MBR2_0100_A1', 'Chocolate PoC New_0240_Line 1')
- `product_name`: Get all recipes for a product
"""
        )
        async def get_recipe(params: GetRecipeInput) -> dict:
            inputs = params.model_dump()
            async with self.tracing.trace_tool("get_recipe", inputs) as span:
                try:
                    result = await product_service.get_recipe(trace_span=span, **inputs)
                    data = result.get("recipes", [])
                    if not data:
                        response = ToolResponse.no_data(
                            suggestions=[
                                "Verify the recipe_id or recipe_name is correct",
                                "Try get_batches to find the recipe_id from a batch response",
                                "Use recipe_name with a partial match like 'MBR1' or 'Chocolate'",
                            ]
                        )
                    else:
                        response = ToolResponse.success(
                            data={
                                "recipes": data,
                                "count": result["count"],
                                "tables_used": result.get("tables_used"),
                                "logic": result.get("logic"),
                            }
                        )
                    self.tracing.set_output(span, response.to_dict())
                    return response.to_dict()
                except Exception as e:
                    self.tracing.record_error(span, e, "get_recipe")
                    self.logger.error("get_recipe failed: %s", e, exc_info=True)
                    return ToolResponse.error(
                        message=str(e),
                        suggestions=[
                            "Verify recipe_id or recipe_name",
                            "Check tRecipe table is accessible",
                        ],
                    ).to_dict()

    def _register_get_products(self) -> None:
        @self.mcp.tool(
            name="get_products",
            description="""Query the product master table (tProduct) — returns ALL products including those never produced.

**Use this tool when the user asks about:**
- "What products do we have available?"
- "What products are in the system?"
- "List all products"
- "How many products do we manufacture?"
- "What is product P00001_FAC1_0002?"
- "Which products have never been used in a batch?"
- "Show me all product versions"

**Why use this instead of get_batches for product questions?**
get_batches only shows products that have run in production.
get_products reads tProduct master data and shows EVERY product,
including those with batch_count=0 (never produced).

**Key Parameters:**
- `product_code`: Filter by code e.g. 'P00001_FAC1_0001' (partial match supported)
- `product_name`: Filter by name (partial match)
- `include_batch_count`: Show how many batches each product has produced (default True)
- `enabled_only`: Only show enabled products (default True)
"""
        )
        async def get_products(params: GetProductsInput) -> dict:
            inputs = params.model_dump()
            async with self.tracing.trace_tool("get_products", inputs) as span:
                try:
                    result = await product_service.get_products(trace_span=span, **inputs)
                    data = result.get("products", [])
                    if not data:
                        response = ToolResponse.no_data(
                            suggestions=[
                                "Try enabled_only=False to include disabled products",
                                "Remove product_name or product_code filter",
                                "Check tProduct table is populated",
                            ]
                        )
                    else:
                        response = ToolResponse.success(
                            data={
                                "products": data,
                                "count": result["count"],
                                "tables_used": result.get("tables_used"),
                                "logic": result.get("logic"),
                            }
                        )
                    self.tracing.set_output(span, response.to_dict())
                    return response.to_dict()
                except Exception as e:
                    self.tracing.record_error(span, e, "get_products")
                    self.logger.error("get_products failed: %s", e, exc_info=True)
                    return ToolResponse.error(
                        message=str(e),
                        suggestions=["Check tProduct table is accessible"],
                    ).to_dict()