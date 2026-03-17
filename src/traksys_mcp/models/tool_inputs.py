from pydantic import BaseModel, Field
from typing import Optional, List


class GetBatchesInput(BaseModel):
    batch_id: Optional[int] = Field(None, description="Specific batch ID to retrieve (tBatch.ID)")
    batch_name: Optional[str] = Field(
        None,
        description="Batch name or code (tBatch.Name ). "
                    "Example: 'AA001' or long codes like '00001_FAC1_00010001_SubPO1_MBR1_0020_A1_1'. "
    )
    system_id: Optional[int] = Field(None, description="Production line/system ID (tBatch.SystemID).")
    system_name: Optional[str] = Field(None, description="Production line/system Name (tSystem.Name).")
    job_id: Optional[int] = Field(None, description="Job/production order ID (tBatch.JobID)")
    time_window: Optional[str] = Field(
        None,
        description="Natural language time expression. Examples: 'yesterday', 'last 7 days', 'this week', '2024-08-31'."
    )
    start_date: Optional[str] = Field(None, description="Explicit start date (YYYY-MM-DD). Overrides time_window.")
    end_date: Optional[str] = Field(None, description="Explicit end date (YYYY-MM-DD). Overrides time_window.")
    state: Optional[int] = Field(
        None,
        description="Batch state filter (tBatch.State)."
    )
    limit: int = Field(default=50, ge=1, le=1000, description="Maximum number of batches to return (1-1000)")


class GetBatchParametersInput(BaseModel):
    batch_id: Optional[int] = Field(None, description="Specific batch ID (tBatch.ID).")
    batch_name: Optional[str] = Field(
        None,
        description="Batch name or code (tBatch.Name). Automatically resolved to numeric ID."
    )
    parameter_names: Optional[List[str]] = Field(
        None,
        description="Parameter names to filter (tParameterDefinition.Name). Example: ['Filling Weight', 'Agitation Speed']."
    )
    deviation_only: bool = Field(
        False,
        description="Return only parameters outside normal range (tParameterDefinition.Min/Max)."
    )
    time_window: Optional[str] = Field(None, description="Natural language time expression for batch selection.")
    start_date: Optional[str] = Field(None, description="Explicit start date (YYYY-MM-DD). Overrides time_window.")
    end_date: Optional[str] = Field(None, description="Explicit end date (YYYY-MM-DD).")
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of parameters to return (1-1000)")


class GetBatchMaterialsInput(BaseModel):
    batch_id: Optional[int] = Field(None, description="Specific batch ID (tBatch.ID). Resolved to JobID internally.")
    batch_name: Optional[str] = Field(None, description="Batch name or code.")
    job_id: Optional[int] = Field(None, description="Direct Job ID (tMaterialUseActual.JobID).")
    material_names: Optional[List[str]] = Field(None, description="Filter by material names (tMaterial.Name).")
    material_codes: Optional[List[str]] = Field(None, description="Filter by material codes (tMaterial.MaterialCode).")
    time_window: Optional[str] = Field(None, description="Natural language time expression for batch selection.")
    start_date: Optional[str] = Field(None, description="Explicit start date (YYYY-MM-DD). Overrides time_window.")
    end_date: Optional[str] = Field(None, description="Explicit end date (YYYY-MM-DD).")
    include_planned_bom: bool = Field(default=True, description="If true, includes planned BOM from _SAPBOM alongside actual consumption for comparison." )
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of material records to return (1-1000)")

class GetBatchDetailsInput(BaseModel):
    batch_id: Optional[int] = Field(None, description="Specific batch ID (tBatch.ID).")
    batch_name: Optional[str] = Field(None, description="Batch name or code (tBatch.Name).")

class GetRecipeInput(BaseModel):
    recipe_id: Optional[int] = Field(
        None, description="Specific recipe ID (tRecipe.ID). Example: 595, 612")
    recipe_name: Optional[str] = Field(
        None, description="Recipe name. Example: 'MBR2_0100_A1', 'Chocolate PoC New_0240_Line 1'")
    product_name: Optional[str] = Field(
        None, description="Filter by product name or code. Example: 'P00001_FAC1_0001'")
    include_steps: bool = Field(True, description="Include recipe step definitions.")
    include_materials: bool = Field(True, description="Include materials required per step.")
    include_parameters: bool = Field(True, description="Include target parameter values per step.")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum recipes to return.")


class GetProductsInput(BaseModel):
    product_id: Optional[int] = Field(None, description="Specific product ID (tProduct.ID).")
    product_name: Optional[str] = Field(
        None, description="Filter by product name or alt name (partial match).")
    product_code: Optional[str] = Field(
        None, description="Filter by product code (partial match). Example: 'P00001_FAC1_0001'")
    enabled_only: bool = Field(True, description="Return only enabled products (default True).")
    include_batch_count: bool = Field(
        True, description="Include how many batches each product has run (default True).")
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum products to return.")


class GetBatchQualityAnalysisInput(BaseModel):
    batch_id: Optional[int] = Field(None, description="Specific batch ID. If provided, time filters are ignored.")
    batch_name: Optional[str] = Field(None, description="Batch name or code. Automatically resolved to numeric ID.")
    product_name: Optional[str] = Field(None, description="Filter by product name (tProduct.Name). Example: 'P00001_FAC1_0001'.")
    system_id: Optional[int] = Field(None, description="Filter by production line/system ID (tBatch.SystemID).")
    system_name: Optional[str] = Field(None, description="Filter by production line/system Name (tSystem.Name).")
    time_window: Optional[str] = Field(None, description="Natural language time expression. Only used when batch_id is not provided.")
    start_date: Optional[str] = Field(None, description="Explicit start date (YYYY-MM-DD). Overrides time_window.")
    end_date: Optional[str] = Field(None, description="Explicit end date (YYYY-MM-DD).")
    limit: int = Field(
        default=100, ge=1, le=1000,
        description="Maximum records per signal type (deviations, remarks, tasks). Default 100, max 1000."
    )


class GetEquipmentStateInput(BaseModel):
    system_id: Optional[int] = Field(None, description="Specific equipment/system ID (tSystem.ID).")
    system_name: Optional[str] = Field(None, description="Equipment name or code (tSystem.Name).")
    area_id: Optional[int] = Field(None, description="Filter equipment by Area ID to see all machines in a zone.")
    include_active_faults: bool = Field(False, description="If true, checks tEvent for any active, unclosed downtime events currently stopping the machine.")
    limit: int = Field(default=50, ge=1, le=500, description="Maximum number of machines to return.")


class GetBatchTasksInput(BaseModel):
    batch_id: Optional[int] = Field(None, description="Specific batch ID (tBatch.ID).")
    batch_name: Optional[str] = Field(None, description="Batch name or code. Automatically resolved to numeric ID.")
    status_filter: Optional[str] = Field(
        None,
        description="Filter by task status: 'completed', 'incomplete', 'pending'. Leave empty for all."
    )
    task_name: Optional[str] = Field(None, description="Filter by task name (partial match).")
    time_window: Optional[str] = Field(None, description="Natural language time expression. Only used when batch_id is not provided.")
    start_date: Optional[str] = Field(None, description="Explicit start date (YYYY-MM-DD). Overrides time_window.")
    end_date: Optional[str] = Field(None, description="Explicit end date (YYYY-MM-DD).")
    limit: int = Field(default=100, ge=1, le=1000,  description="Maximum number of task records to return (1-1000).")



class CalculateOEEInput(BaseModel):
    """Input schema for calculate_oee tool."""

    line: Optional[str] = Field(
        None,
        description="Equipment/line name (tSystem.Name). Example: 'E1'. If omitted, aggregates across all lines."
    )

    start_date: str = Field(
        ...,
        description="Explicit start date in ISO format (YYYY-MM-DD). Required."
    )

    end_date: str = Field(
        ...,
        description="Explicit end date in ISO format (YYYY-MM-DD). Required."
    )

    granularity: Optional[str] = Field(
        default="daily",
        description="How to group results: 'daily', 'weekly', 'shift'."
    )

    breakdown: bool = Field(
        default=True,
        description="If true, includes Availability, Performance, Quality components separately."
    )


class AnalyzeTaskComplianceInput(BaseModel):
    system_name: Optional[str] = Field(None, description="Filter by production line name (tSystem.Name). Leave empty for all lines.")
    system_id: Optional[int] = Field(None, description="Filter by production line ID (tSystem.ID).")
    product_name: Optional[str] = Field(None, description="Filter by product name (tProduct.Name).")
    time_window: Optional[str] = Field(None, description="Natural language time expression. Leave empty for all available data.")
    start_date: Optional[str] = Field(None, description="Explicit start date (YYYY-MM-DD). Overrides time_window.")
    end_date: Optional[str] = Field(None, description="Explicit end date (YYYY-MM-DD).")
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of task type groups to return.")