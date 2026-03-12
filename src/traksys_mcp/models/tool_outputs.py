from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ResponseStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    NO_DATA = "no_data"
    ERROR = "error"


class TimeResolutionInfo(BaseModel):
    requested: dict[str, str]
    actual: dict[str, str]
    fallback_triggered: bool
    message: str | None = None
    suggestion_message: str | None = None
    available_date_range: dict[str, str] | None = None


class ToolResponse(BaseModel):
    """Universal response wrapper for all MCP tools."""

    model_config = {"frozen": True}

    status: ResponseStatus = Field(default=ResponseStatus.SUCCESS)
    count: int = Field(default=0, ge=0)
    data: Any | None = Field(default=None)
    time_info: TimeResolutionInfo | None = Field(default=None)
    message: str | None = Field(default=None)
    suggestions: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @model_validator(mode="after")
    def set_count_from_data(self) -> "ToolResponse":
        """Auto-populate count from data length when not explicitly set."""
        if self.count == 0 and self.data is not None:
            if isinstance(self.data, (list, tuple, set, dict)):
                object.__setattr__(self, "count", len(self.data))
            else:
                object.__setattr__(self, "count", 1)
        return self

    @classmethod
    def success(
        cls,
        data: Any,
        time_info: TimeResolutionInfo | None = None,
        suggestions: list[str] | None = None,
    ) -> "ToolResponse":
        return cls(status=ResponseStatus.SUCCESS, data=data, time_info=time_info, suggestions=suggestions or [])

    @classmethod
    def partial(
        cls,
        data: Any,
        time_info: TimeResolutionInfo,
        message: str,
        suggestions: list[str] | None = None,
    ) -> "ToolResponse":
        return cls(status=ResponseStatus.PARTIAL, data=data, time_info=time_info, message=message, suggestions=suggestions or [])

    @classmethod
    def no_data(
        cls,
        suggestions: list[str],
        time_info: TimeResolutionInfo | None = None,
    ) -> "ToolResponse":
        return cls(status=ResponseStatus.NO_DATA, data=[], count=0, time_info=time_info, suggestions=suggestions)

    @classmethod
    def error(
        cls,
        message: str,
        suggestions: list[str] | None = None,
    ) -> "ToolResponse":
        return cls(
            status=ResponseStatus.ERROR,
            data=None,
            count=0,
            message=message,
            suggestions=suggestions or ["Check database connection", "Verify input parameters"],
        )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)

    def __repr__(self) -> str:
        data_type = type(self.data).__name__ if self.data is not None else "None"
        return (
            f"ToolResponse(status={self.status}, count={self.count}, "
            f"data_type={data_type}, suggestions={len(self.suggestions)})"
        )