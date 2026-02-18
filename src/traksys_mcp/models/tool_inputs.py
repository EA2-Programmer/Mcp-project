"""
Pydantic input models for all MCP tools.

These schemas provide:
- Type validation
- Field descriptions (Claude reads these!)
- Default values
- Range constraints
"""

from pydantic import BaseModel, Field
from typing import Optional


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