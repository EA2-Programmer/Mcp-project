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
            description="Specific batch ID (tBatchParameter.BatchID). If provided, time filters are ignored."
        )

        parameter_names: Optional[List[str]] = Field(
            None,
            description="List of parameter names to filter (e.g. ['Temperature', 'Pressure', 'Speed']). From tParameterDefinition.Name"
        )

        step_name: Optional[str] = Field(
            None,
            description="Batch step name filter (BatchStepID linked). TODO: join tBatchStep if table exists."
        )

        deviation_only: bool = Field(
            False,
            description="Return ONLY parameters outside normal range (uses tParameterDefinition.Min/Max). "
                        "Extend with _CPR (L_PAR, L_NOR, H_NOR, H_PAR) for advanced deviation logic."
        )

        time_window: Optional[str] = Field(
            None,
            description="Natural language time expression for the *batches* these parameters belong to. "
                        "Examples: 'yesterday', 'last 7 days', 'this week', '2024-08-31'. "
                        "Intelligent fallback via DataAvailabilityCache on tBatch."
        )

        start_date: Optional[str] = Field(
            None,
            description="Explicit start date (YYYY-MM-DD). Overrides time_window if both provided."
        )

        end_date: Optional[str] = Field(
            None,
            description="Explicit end date (YYYY-MM-DD)."
        )

        limit: int = Field(
            default=100,
            ge=1,
            le=1000,
            description="Maximum number of parameters to return"
        )

class GetBatchMaterialsInput(BaseModel):
    """Input schema for get_batch_materials tool."""

    batch_id: Optional[int] = Field(
        None,
        description="Specific batch ID to retrieve material usage for (tMaterialUseActual.BatchID)"
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
            "Examples: 'yesterday', 'last 7 days', 'this week', '2025-12-01 to 2025-12-15'. "
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