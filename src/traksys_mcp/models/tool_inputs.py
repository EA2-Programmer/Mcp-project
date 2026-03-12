"""
Pydantic input models for all MCP tools.

These schemas provide:
- Type validation
- Field descriptions (Claude reads these!)
- Default values
- Range constraints
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class GetBatchesInput(BaseModel):
    """Input schema for get_batches tool."""

    batch_id: Optional[int] = Field(
        None,
        description="Specific batch ID to retrieve (tBatch.ID)"
    )

    batch_name: Optional[str] = Field(
        None,
        description="Batch name or code (tBatch.Name or AltName). "
                    "Example: 'AA001' or long codes like '00001_FAC1_00010001_SubPO1_MBR1_0020_A1_1'. "
                    "The system automatically resolves this to the numeric ID."
    )

    system_id: Optional[int] = Field(
        None,
        description="Production line/system ID (tBatch.SystemID). Use this to filter by line."
    )

    job_id: Optional[int] = Field(
        None,
        description="Job/production order ID (tBatch.JobID)"
    )

    time_window: Optional[str] = Field(
        None,
        description=(
            "Natural language time expression. Examples: 'yesterday', 'last 7 days', "
            "'this week', '2024-08-31'. System will intelligently fall back to available "
            "data if requested dates don't exist."
        )
    )

    start_date: Optional[str] = Field(
        None,
        description=(
            "Explicit start date in ISO format (YYYY-MM-DD). Example: '2024-08-25'. "
            "If provided, overrides time_window."
        )
    )

    end_date: Optional[str] = Field(
        None,
        description=(
            "Explicit end date in ISO format (YYYY-MM-DD). Example: '2024-08-31'. "
            "If provided, overrides time_window."
        )
    )

    state: Optional[int] = Field(
        None,
        description=(
            "Batch state filter (tBatch.State - integer). "
            "Common values might be: 0=Created, 1=In Progress, 2=Completed (verify in your data)"
        )
    )

    limit: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Maximum number of batches to return (1-1000)"
    )


class GetBatchParametersInput(BaseModel):
    """Input schema for get_batch_parameters tool."""

    batch_id: Optional[int] = Field(
        None,
        description="Specific batch ID (tBatch.ID). Use this when you know the numeric ID."
    )

    batch_name: Optional[str] = Field(
        None,
        description="Batch name or code (tBatch.Name or AltName). "
                    "Example: 'AA001' or long codes like '00001_FAC1_...'. "
                    "The system automatically resolves this to the numeric ID."
    )

    parameter_names: Optional[List[str]] = Field(
        None,
        description="List of parameter names to filter (e.g. ['Temperature', 'Pressure', 'Speed']). From tParameterDefinition.Name"
    )

    deviation_only: bool = Field(
        False,
        description="Return ONLY parameters outside normal range (uses tParameterDefinition.Min/Max). "
                    "Extend with _CPR (L_PAR, L_NOR, H_NOR, H_PAR) for advanced deviation logic."
    )

    time_window: Optional[str] = Field(
        None,
        description=(
            "Natural language time expression for the *batches* these parameters belong to. "
            "Examples: 'yesterday', 'last 7 days', 'this week', '2024-08-31'. "
            "System will intelligently fall back to available data if requested dates don't exist."
        )
    )

    start_date: Optional[str] = Field(
        None,
        description=(
            "Explicit start date in ISO format (YYYY-MM-DD). Example: '2024-08-25'. "
            "If provided, overrides time_window."
        )
    )

    end_date: Optional[str] = Field(
        None,
        description=(
            "Explicit end date in ISO format (YYYY-MM-DD). Example: '2024-08-31'. "
            "If provided, overrides time_window."
        )
    )

    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of parameters to return (1-1000)"
    )


class GetBatchMaterialsInput(BaseModel):
    """Input schema for get_batch_materials tool."""

    batch_id: Optional[int] = Field(
        None,
        description="Specific batch ID (tBatch.ID). System will resolve to JobID internally."
    )

    batch_name: Optional[str] = Field(
        None,
        description="Batch name or code (tBatch.Name). "
                    "Example: 'AA001' or long codes like '00001_FAC1_...'. "
                    "The system automatically resolves this to the numeric ID."
    )

    job_id: Optional[int] = Field(          # Added as requested
        None,
        description="Direct Job ID (tMaterialUseActual.JobID). Use this when you know the JobID."
    )

    material_names: Optional[List[str]] = Field(
        None,
        description="Filter by material names (tMaterial.Name). Example: ['Sugar', 'Water', 'Citric Acid']"
    )

    material_codes: Optional[List[str]] = Field(
        None,
        description="Filter by material codes (tMaterial.MaterialCode). Example: ['MAT-001', 'RAW-SUG-01']"
    )

    time_window: Optional[str] = Field(
        None,
        description=(
            "Natural language time expression for the batches these materials were used in. "
            "Examples: 'yesterday', 'last 7 days', 'this week'. "
            "System automatically falls back to available data if requested dates have no records."
        )
    )

    start_date: Optional[str] = Field(
        None,
        description="Explicit start date in ISO format (YYYY-MM-DD). Overrides time_window if both provided."
    )

    end_date: Optional[str] = Field(
        None,
        description="Explicit end date in ISO format (YYYY-MM-DD)."
    )

    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of material usage records to return (1–1000)"
    )


class GetEquipmentStateInput(BaseModel):
    """Input schema for get_equipment_state tool."""

    system_id: Optional[int] = Field(
        None,
        description="Specific equipment/system ID (tSystem.ID)."
    )

    system_name: Optional[str] = Field(
        None,
        description="Equipment name or code (tSystem.Name or AltName). Example: 'Packer 01'."
    )

    area_id: Optional[int] = Field(
        None,
        description="Filter equipment by Area ID. Use this to see status of an entire department."
    )

    time_window: Optional[str] = Field(
        None,
        description=(
            "Natural language time expression for performance analysis. "
            "Examples: 'yesterday', 'last 7 days', 'this week'. "
            "Default behavior (without time) shows 'Current Status'."
        )
    )

    start_date: Optional[str] = Field(
        None,
        description="Explicit start date in ISO format (YYYY-MM-DD)."
    )

    end_date: Optional[str] = Field(
        None,
        description="Explicit end date in ISO format (YYYY-MM-DD)."
    )

    include_oee: bool = Field(
        False,
        description="If true, calculates OEE, Availability, and Performance metrics for the period."
    )

    include_tags: bool = Field(
        False,
        description="If true, fetches real-time tag values (Speed, Pressure, etc.) from tTag."
    )

    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of records to return."
    )



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
    