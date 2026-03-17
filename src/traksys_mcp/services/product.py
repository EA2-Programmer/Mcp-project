"""
Contains products that exist in the database and the recipes used during
manufacturing
"""

import logging
from typing import Any

from src.traksys_mcp.core.database import execute_query
from src.traksys_mcp.core.utils import rows_to_dicts

logger = logging.getLogger(__name__)


async def get_recipe(
        recipe_id: int | None = None,
        recipe_name: str | None = None,
        product_id: int | None = None,
        product_name: str | None = None,
        include_steps: bool = True,
        include_materials: bool = True,
        include_parameters: bool = True,
        limit: int = 10,
        trace_span=None,
) -> dict:
    """
    Query recipe definitions with steps, materials, and parameters.
    Recipe → Batch: tRecipe → tJobBatch.RecipeID → tJob → tBatch
    """
    # Resolve recipe_name → ID
    if recipe_name and recipe_id is None:
        _, rows = await execute_query(
            "SELECT TOP 1 ID FROM tRecipe WHERE Name = ? OR AltName = ? ORDER BY ID DESC",
            (recipe_name, recipe_name),
            trace_span=trace_span,
        )
        if rows and rows[0][0]:
            recipe_id = rows[0][0]
            logger.info("Resolved recipe_name '%s' → ID %s", recipe_name, recipe_id)

    # Resolve product_name → ID
    if product_name and product_id is None:
        _, rows = await execute_query(
            "SELECT TOP 1 ID FROM tProduct WHERE Name = ? OR ProductCode = ?",
            (product_name, product_name),
            trace_span=trace_span,
        )
        if rows and rows[0][0]:
            product_id = rows[0][0]

    safe_limit = max(1, min(int(limit), 500))

    where_parts: list[str] = []
    params: list[Any] = []
    if recipe_id is not None:
        where_parts.append("r.ID = ?")
        params.append(recipe_id)
    if product_id is not None:
        where_parts.append("r.ProductID = ?")
        params.append(product_id)

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"

    sql_recipes = f"""
        SELECT TOP {safe_limit}
            r.ID                        AS recipe_id,
            r.Name                      AS recipe_name,
            r.AltName                   AS recipe_alt_name,
            r.Description               AS description,
            r.Version                   AS version,
            r.VersionState              AS version_state,
            p.ID                        AS product_id,
            p.Name                      AS product_name,
            p.ProductCode               AS product_code,
            s.Name                      AS system_name,
            r.PlannedBatchSize          AS planned_batch_size,
            r.PlannedBatchSizeUnits     AS planned_batch_size_units,
            r.PlannedBatchDurationSeconds AS planned_duration_seconds,
            r.Enabled                   AS enabled
        FROM tRecipe r
        LEFT JOIN tProduct p ON r.ProductID = p.ID
        LEFT JOIN tSystem  s ON r.SystemID  = s.ID
        WHERE {where_clause}
        ORDER BY r.ID DESC
    """
    columns, rows = await execute_query(sql_recipes, tuple(params), trace_span=trace_span)
    recipes = rows_to_dicts(columns, rows)

    if not recipes:
        return {
            "recipes": [], "count": 0,
            "message": f"No recipe found for {'ID ' + str(recipe_id) if recipe_id else recipe_name or 'given filters'}"
        }

    result_recipes = []
    for recipe in recipes:
        rid = recipe["recipe_id"]
        entry = dict(recipe)

        if include_steps:
            sql_steps = """
                SELECT
                    rsd.ID                      AS step_id,
                    rsd.StartSequence           AS sequence,
                    rsd.PlannedDurationSeconds  AS planned_duration_seconds,
                    fd.Name                     AS step_name,
                    fd.Description              AS step_description
                FROM tRecipeStepDefinition rsd
                LEFT JOIN tFunctionDefinition fd ON rsd.FunctionDefinitionID = fd.ID
                WHERE rsd.RecipeID = ?
                ORDER BY rsd.StartSequence
            """
            columns, rows = await execute_query(sql_steps, (rid,), trace_span=trace_span)
            entry["steps"] = rows_to_dicts(columns, rows)
            entry["steps_count"] = len(entry["steps"])

        if include_materials:
            sql_mats = """
                SELECT
                    rsdm.RecipeStepDefinitionID AS step_id,
                    rsd.StartSequence           AS sequence,
                    m.Name                      AS material_name,
                    m.MaterialCode              AS material_code,
                    rsdm.Percentage             AS percentage
                FROM tRecipeStepDefinitionMaterial rsdm
                INNER JOIN tRecipeStepDefinition rsd ON rsdm.RecipeStepDefinitionID = rsd.ID
                INNER JOIN tMaterial m              ON rsdm.MaterialID              = m.ID
                WHERE rsd.RecipeID = ?
                ORDER BY rsd.StartSequence, rsdm.DisplayOrder
            """
            columns, rows = await execute_query(sql_mats, (rid,), trace_span=trace_span)
            entry["recipe_materials"] = rows_to_dicts(columns, rows)
            entry["recipe_materials_count"] = len(entry["recipe_materials"])

        if include_parameters:
            sql_params = """
                SELECT
                    rp.RecipeStepDefinitionID   AS step_id,
                    rsd.StartSequence           AS sequence,
                    pd.Name                     AS parameter_name,
                    pd.Description              AS parameter_description,
                    rp.Value                    AS target_value,
                    pd.MinimumValue             AS min_allowed,
                    pd.MaximumValue             AS max_allowed,
                    pd.DefaultValue             AS default_value,
                    pd.DataType                 AS data_type
                FROM tRecipeParameter rp
                INNER JOIN tRecipeStepDefinition rsd ON rp.RecipeStepDefinitionID = rsd.ID
                LEFT  JOIN tParameterDefinition  pd  ON rp.ParameterDefinitionID  = pd.ID
                WHERE rp.RecipeID = ?
                ORDER BY rsd.StartSequence
            """
            columns, rows = await execute_query(sql_params, (rid,), trace_span=trace_span)
            entry["recipe_parameters"] = rows_to_dicts(columns, rows)
            entry["recipe_parameters_count"] = len(entry["recipe_parameters"])

        sql_batches = """
            SELECT TOP 10
                b.ID                AS batch_id,
                b.Name              AS batch_name,
                b.State             AS state,
                CONVERT(nvarchar(30), b.StartDateTime, 126) AS batch_start,
                CONVERT(nvarchar(30), b.EndDateTime,   126) AS batch_end,
                j.ID                AS job_id,
                j.Name              AS job_name,
                s.Name              AS system_name
            FROM tJobBatch jb
            INNER JOIN tJob    j ON jb.JobID    = j.ID
            INNER JOIN tBatch  b ON b.JobID     = j.ID
            INNER JOIN tSystem s ON b.SystemID  = s.ID
            WHERE jb.RecipeID = ?
            ORDER BY b.StartDateTime DESC
        """
        columns, rows = await execute_query(sql_batches, (rid,), trace_span=trace_span)
        entry["batches_using_recipe"] = rows_to_dicts(columns, rows)
        entry["batches_count"] = len(entry["batches_using_recipe"])

        result_recipes.append(entry)

    logger.info("get_recipe → %d recipes (recipe_id=%s, recipe_name=%s)",
                len(result_recipes), recipe_id, recipe_name)

    return {
        "recipes": result_recipes,
        "count": len(result_recipes),
        "tables_used": [
            "tRecipe", "tRecipeStepDefinition", "tRecipeStepDefinitionMaterial",
            "tRecipeParameter", "tParameterDefinition", "tJobBatch", "tJob", "tBatch",
            "tProduct", "tSystem"
        ],
        "logic": (
            "Recipes define the manufacturing procedure for a product. "
            "Steps come from tRecipeStepDefinition, materials per step from "
            "tRecipeStepDefinitionMaterial, and target parameter values from "
            "tRecipeParameter joined to tParameterDefinition. "
            "Batches that used this recipe are found via tJobBatch.RecipeID → tJob → tBatch."
        ),
    }


async def get_products(
        product_id: int | None = None,
        product_name: str | None = None,
        product_code: str | None = None,
        enabled_only: bool = True,
        include_batch_count: bool = True,
        limit: int = 100,
        trace_span=None,
) -> dict:
    """
    Query all products from tProduct master table.
    Includes batch count so you can see which products have actually been used.
    Returns BOTH used and unused products — unlike get_batches which only shows
    products that have run.
    """
    where_parts: list[str] = []
    params: list[Any] = []

    if enabled_only:
        where_parts.append("p.Enabled = 1")
    if product_id is not None:
        where_parts.append("p.ID = ?")
        params.append(product_id)
    if product_name:
        where_parts.append("(p.Name LIKE ? OR p.AltName LIKE ?)")
        params.extend([f"%{product_name}%", f"%{product_name}%"])
    if product_code:
        where_parts.append("p.ProductCode LIKE ?")
        params.append(f"%{product_code}%")

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"
    safe_limit = max(1, min(int(limit), 1000))

    if include_batch_count:
        sql = f"""
            SELECT TOP {safe_limit}
                p.ID                AS product_id,
                p.Name              AS product_name,
                p.AltName           AS product_alt_name,
                p.ProductCode       AS product_code,
                p.Description       AS description,
                p.Version           AS version,
                p.VersionState      AS version_state,
                p.StandardSize      AS standard_size,
                p.StandardUnits     AS standard_units,
                p.Enabled           AS enabled,
                COUNT(b.ID)         AS batch_count,
                MAX(CONVERT(nvarchar(30), b.StartDateTime, 126)) AS last_batch_date
            FROM tProduct p
            LEFT JOIN tJob   j ON j.ProductID = p.ID
            LEFT JOIN tBatch b ON b.JobID     = j.ID
            WHERE {where_clause}
            GROUP BY p.ID, p.Name, p.AltName, p.ProductCode, p.Description,
                     p.Version, p.VersionState, p.StandardSize,
                     p.StandardUnits, p.Enabled
            ORDER BY p.ID
        """
    else:
        sql = f"""
            SELECT TOP {safe_limit}
                p.ID                AS product_id,
                p.Name              AS product_name,
                p.AltName           AS product_alt_name,
                p.ProductCode       AS product_code,
                p.Description       AS description,
                p.Version           AS version,
                p.VersionState      AS version_state,
                p.StandardSize      AS standard_size,
                p.StandardUnits     AS standard_units,
                p.Enabled           AS enabled
            FROM tProduct p
            WHERE {where_clause}
            ORDER BY p.ID
        """

    columns, rows = await execute_query(sql, tuple(params), trace_span=trace_span)
    products = rows_to_dicts(columns, rows)

    logger.info("get_products → %d products", len(products))

    return {
        "products": products,
        "count": len(products),
        "tables_used": ["tProduct", "tJob", "tBatch"] if include_batch_count else ["tProduct"],
        "logic": (
            "Direct query of tProduct master table. Unlike get_batches, this returns ALL "
            "products including those never used in production (batch_count=0). "
            "batch_count shows how many batches have run for each product."
        ),
    }