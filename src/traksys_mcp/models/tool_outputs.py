"""
Standardized response format for all MCP tools.

Uses Pydantic v2 for validation, type safety, and OpenAPI schema generation.
Follows Python 3.10+ typing conventions.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ResponseStatus(str, Enum):
    """Valid response status values."""

    SUCCESS = "success"
    PARTIAL = "partial"  # Data returned with fallback/limitations
    NO_DATA = "no_data"  # Query valid but no results
    ERROR = "error"  # Query failed


class TimeResolutionInfo(BaseModel):
    """Metadata about time window resolution and fallback behavior."""

    requested: dict[str, str]  # e.g., {"start": "2024-01-01", "end": "2024-01-07"}
    actual: dict[str, str]  # What was actually queried
    fallback_triggered: bool
    message: str | None = None
    suggestion_message: str | None = None
    available_date_range: dict[str, str] | None = None


class ToolResponse(BaseModel):
    """
    Universal response wrapper for all MCP tools.

    Ensures consistent structure for AI agent parsing and monitoring.
    Frozen=True prevents accidental mutation after creation.
    """

    model_config = {"frozen": True}  # Immutability for safety

    status: ResponseStatus = Field(
        default=ResponseStatus.SUCCESS,
        description="Outcome of the tool execution",
    )
    count: int = Field(
        default=0,
        ge=0,
        description="Number of items in data (if applicable)",
    )
    data: Any | None = Field(
        default=None,
        description="The actual payload — structure depends on the tool",
    )
    time_info: TimeResolutionInfo | None = Field(
        default=None,
        description="Time resolution metadata when fallback occurred",
    )
    message: str | None = Field(
        default=None,
        description="Human-readable message (errors, fallback explanations)",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Actionable suggestions for empty/error results",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp of response generation",
    )


    @model_validator(mode="after")
    def set_count_from_data(self) -> "ToolResponse":
        """
        Auto-calculate count from data if not explicitly provided.

        Runs AFTER all field validation, ensuring data is available.
        Uses object.__setattr__ because model is frozen.
        """
        if self.count == 0 and self.data is not None:
            if isinstance(self.data, list | tuple | set | dict):
                object.__setattr__(self, "count", len(self.data))
            elif self.data is not None:
                object.__setattr__(self, "count", 1)
        return self



    @classmethod
    def success(
        cls,
        data: Any,
        time_info: TimeResolutionInfo | None = None,
        suggestions: list[str] | None = None,
    ) -> "ToolResponse":
        """Create a success response."""
        return cls(
            status=ResponseStatus.SUCCESS,
            data=data,
            time_info=time_info,
            suggestions=suggestions or [],
        )

    @classmethod
    def partial(
        cls,
        data: Any,
        time_info: TimeResolutionInfo,
        message: str,
        suggestions: list[str] | None = None,
    ) -> "ToolResponse":
        """Create a partial success response (data returned with fallback)."""
        return cls(
            status=ResponseStatus.PARTIAL,
            data=data,
            time_info=time_info,
            message=message,
            suggestions=suggestions or [],
        )

    @classmethod
    def no_data(
        cls,
        suggestions: list[str],
        time_info: TimeResolutionInfo | None = None,
    ) -> "ToolResponse":
        """Create a no-data response with helpful suggestions."""
        return cls(
            status=ResponseStatus.NO_DATA,
            data=[],
            count=0,
            time_info=time_info,
            suggestions=suggestions,
        )

    @classmethod
    def error(
        cls,
        message: str,
        suggestions: list[str] | None = None,
    ) -> "ToolResponse":
        """Create an error response."""
        return cls(
            status=ResponseStatus.ERROR,
            data=None,
            count=0,
            message=message,
            suggestions=suggestions or [
                "Check database connection",
                "Verify input parameters",
            ],
        )


    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON-RPC response."""
        return self.model_dump(exclude_none=True)

    def __repr__(self) -> str:
        """Debug-friendly representation."""
        data_type = type(self.data).__name__ if self.data is not None else "None"
        # ResponseStatus inherits from str, so self.status is already the string value
        return (
            f"ToolResponse(status={self.status}, count={self.count}, "
            f"data_type={data_type}, suggestions={len(self.suggestions)})"
        )