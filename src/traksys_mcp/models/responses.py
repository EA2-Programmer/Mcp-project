from typing import Any, List, Optional, Dict
from datetime import datetime


class ToolResponse:
    """Consistent response format for all tools."""

    def __init__(
            self,
            data: Any,
            status: str = "success",  # success, partial, no_data, error
            count: Optional[int] = None,
            time_info: Optional[Dict] = None,
            message: Optional[str] = None,
            suggestions: Optional[List[str]] = None
    ):
        self.data = data
        self.status = status
        self.count = count if count is not None else (len(data) if data else 0)
        self.time_info = time_info
        self.message = message
        self.suggestions = suggestions or []

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON response."""
        result = {
            "status": self.status,
            "count": self.count,
            "data": self.data
        }

        if self.time_info:
            result["time_info"] = self.time_info

        if self.message:
            result["message"] = self.message

        if self.suggestions:
            result["suggestions"] = self.suggestions

        return result

    @classmethod
    def success(cls, data: Any, time_info: Optional[Dict] = None):
        """Create success response."""
        return cls(data=data, status="success", time_info=time_info)

    @classmethod
    def partial(cls, data: Any, time_info: Dict, message: str):
        """Create partial success (with fallback)."""
        return cls(
            data=data,
            status="partial",
            time_info=time_info,
            message=message
        )

    @classmethod
    def no_data(cls, suggestions: List[str], time_info: Optional[Dict] = None):
        """Create no data response with suggestions."""
        return cls(
            data=[],
            status="no_data",
            count=0,
            time_info=time_info,
            suggestions=suggestions
        )

    @classmethod
    def error(cls, error: str, suggestions: List[str] = None):
        """Create error response."""
        return cls(
            data=None,
            status="error",
            count=0,
            message=error,
            suggestions=suggestions or ["Check database connection", "Verify input parameters"]
        )