from pydantic import BaseModel, Field
from typing import Optional, List


class GetBatchesInput(BaseModel):
    batch_id: Optional[int] = Field(None, description="Specific batch ID to retrieve (tBatch.ID)")
    batch_name: Optional[str] = Field(
        None,
        description="Batch name or code (tBatch.Name or AltName). "
                    "Example: 'AA001' or long codes like '00001_FAC1_00010001_SubPO1_MBR1_0020_A1_1'. "
                    "The system automatically resolves this to the numeric ID."
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
        description="Batch state filter (tBatch.State). Common values: 0=Created, 1=In Progress, 2=Completed (verify in your data)."
    )
    limit: int = Field(default=50, ge=1, le=1000, description="Maximum number of batches to return (1-1000)")


class GetBatchParametersInput(BaseModel):
    batch_id: Optional[int] = Field(None, description="Specific batch ID (tBatch.ID).")
    batch_name: Optional[str] = Field(
        None,
        description="Batch name or code (tBatch.Name or AltName). Automatically resolved to numeric ID."
    )
    parameter_names: Optional[List[str]] = Field(
        None,
        description="Parameter names to filter (tParameterDefinition.Name). Example: ['Temperature', 'Pressure']."
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
    batch_name: Optional[str] = Field(None, description="Batch name or code. Automatically resolved to numeric ID.")
    job_id: Optional[int] = Field(None, description="Direct Job ID (tMaterialUseActual.JobID).")
    material_names: Optional[List[str]] = Field(None, description="Filter by material names (tMaterial.Name).")
    material_codes: Optional[List[str]] = Field(None, description="Filter by material codes (tMaterial.MaterialCode).")
    time_window: Optional[str] = Field(None, description="Natural language time expression for batch selection.")
    start_date: Optional[str] = Field(None, description="Explicit start date (YYYY-MM-DD). Overrides time_window.")
    end_date: Optional[str] = Field(None, description="Explicit end date (YYYY-MM-DD).")
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of material records to return (1-1000)")


class GetBatchDetailsInput(BaseModel):
    batch_id: Optional[int] = Field(None, description="Specific batch ID (tBatch.ID).")
    batch_name: Optional[str] = Field(None, description="Batch name or code (tBatch.Name or AltName). Automatically resolved to numeric ID.")


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
    system_name: Optional[str] = Field(None, description="Equipment name or code (tSystem.Name or AltName).")
    area_id: Optional[int] = Field(None, description="Filter equipment by Area ID.")
    time_window: Optional[str] = Field(None, description="Natural language time expression for performance analysis.")
    start_date: Optional[str] = Field(None, description="Explicit start date (YYYY-MM-DD).")
    end_date: Optional[str] = Field(None, description="Explicit end date (YYYY-MM-DD).")
    include_oee: bool = Field(False, description="If true, calculates availability and runtime metrics for the period.")
    include_tags: bool = Field(False, description="If true, fetches real-time tag values from tTag.")
    limit: int = Field(default=50, ge=1, le=500, description="Maximum number of records to return.")


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
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of task records to return (1-1000).")


class AnalyzeTaskComplianceInput(BaseModel):
    system_name: Optional[str] = Field(None, description="Filter by production line name (tSystem.Name). Leave empty for all lines.")
    system_id: Optional[int] = Field(None, description="Filter by production line ID (tSystem.ID).")
    product_name: Optional[str] = Field(None, description="Filter by product name (tProduct.Name).")
    time_window: Optional[str] = Field(None, description="Natural language time expression. Leave empty for all available data.")
    start_date: Optional[str] = Field(None, description="Explicit start date (YYYY-MM-DD). Overrides time_window.")
    end_date: Optional[str] = Field(None, description="Explicit end date (YYYY-MM-DD).")
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of task type groups to return.")