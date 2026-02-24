"""
Time resolution service with intelligent fallback.

Converts natural language time expressions to datetime windows,
checking against available data and clamping when necessary.
"""

from datetime import datetime, date, time, timezone, timedelta
import re
import logging
from typing import TYPE_CHECKING

from src.traksys_mcp.core.exceptions import TrakSYSError

if TYPE_CHECKING:
    from data_availability import DataAvailabilityCache

logger = logging.getLogger(__name__)

# Explicit time boundaries for day windows
DAY_START = time(0, 0, 0)
DAY_END = time(23, 59, 59, 999999)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TimeResolutionError(TrakSYSError):
    """Raised when a time expression cannot be parsed or resolved."""
    pass


# ---------------------------------------------------------------------------
# Value Objects
# ---------------------------------------------------------------------------

class TimeWindow:
    """Represents a time range with timezone-aware datetimes."""

    def __init__(self, start: datetime, end: datetime):
        self.start = start
        self.end = end

    def to_dict(self) -> dict[str, str]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
        }

    def __repr__(self) -> str:
        return f"TimeWindow(start={self.start.isoformat()}, end={self.end.isoformat()})"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class TimeResolutionService:
    """
    Converts natural language time expressions to datetime windows.

    Checks the requested window against available data in the database
    and clamps to the actual range when needed, returning a fallback
    message the LLM can surface to the user.
    """

    def __init__(self, data_cache: "DataAvailabilityCache"):
        self.cache = data_cache

    async def resolve(self, expression: str, table: str = "tBatch") -> dict:
        """
        Parse time expression and return window with fallback info.

        Returns:
            {
                "requested": {"start": "...", "end": "..."},
                "actual":    {"start": "...", "end": "..."},
                "fallback_triggered": bool,
                "message": str | None
            }
        """
        # Step 1: Parse expression to target window
        try:
            target = self._parse_expression(expression)
        except TimeResolutionError as e:
            logger.warning("Time expression parse failed: '%s' → %s", expression, e)
            target = self._default_window()
            return self._apply_fallback(
                target,
                f"Could not understand '{expression}'. Using last 7 days instead."
            )

        # Step 2: Check if target exists in database
        available = await self.cache.get_range(table)
        if not available:
            return {
                "requested": target.to_dict(),
                "actual": target.to_dict(),
                "fallback_triggered": False,
                "message": None,
            }

        min_date, max_date = available
        target_start_date = target.start.date()
        target_end_date = target.end.date()

        # Step 3: Check if target window fits inside available range
        if (min_date <= target_start_date <= max_date and
                min_date <= target_end_date <= max_date):
            return {
                "requested": target.to_dict(),
                "actual": target.to_dict(),
                "fallback_triggered": False,
                "message": None,
            }

        # Step 4: Clamp to available range
        actual_start = self._clamp_date(target_start_date, min_date, max_date)
        actual_end = self._clamp_date(target_end_date, min_date, max_date)

        actual_window = TimeWindow(
            start=datetime.combine(actual_start, DAY_START, tzinfo=timezone.utc),
            end=datetime.combine(actual_end, DAY_END, tzinfo=timezone.utc),
        )

        return {
            "requested": target.to_dict(),
            "actual": actual_window.to_dict(),
            "fallback_triggered": True,
            "message": self._generate_message(
                expression,
                target_start_date,
                target_end_date,
                actual_start,
                actual_end,
                min_date,
                max_date,
            ),
        }

    # -----------------------------------------------------------------------
    # Parsing
    # -----------------------------------------------------------------------

    def _parse_expression(self, expr: str) -> TimeWindow:
        """
        Parse natural language time expressions into TimeWindow objects.

        Supported patterns:
            - "yesterday"
            - "last N days" / "last N day"
            - "this week"  (Monday to now, week-to-date)
            - "YYYY-MM-DD" (exact date)
            - "YYYY-MM-DD to YYYY-MM-DD" (explicit range)

        All times are UTC.
        """
        expr = expr.lower().strip()
        now = datetime.now(timezone.utc)

        # Yesterday
        if expr == "yesterday":
            day = (now - timedelta(days=1)).date()
            return TimeWindow(
                start=datetime.combine(day, DAY_START, tzinfo=timezone.utc),
                end=datetime.combine(day, DAY_END, tzinfo=timezone.utc),
            )

        # Last N days
        match = re.match(r"last (\d+) days?", expr)
        if match:
            days = int(match.group(1))
            start = (now - timedelta(days=days)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return TimeWindow(start=start, end=now)

        # This week — Monday to now (week-to-date, not full future week)
        if expr == "this week":
            start = (now - timedelta(days=now.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return TimeWindow(start=start, end=now)

        # Date range: "2024-08-01 to 2024-08-31"
        range_match = re.match(
            r"(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})", expr
        )
        if range_match:
            try:
                start_date = datetime.strptime(range_match.group(1), "%Y-%m-%d").date()
                end_date = datetime.strptime(range_match.group(2), "%Y-%m-%d").date()
            except ValueError:
                raise TimeResolutionError(
                    f"Invalid date range: '{range_match.group(1)} to {range_match.group(2)}'"
                )
            return TimeWindow(
                start=datetime.combine(start_date, DAY_START, tzinfo=timezone.utc),
                end=datetime.combine(end_date, DAY_END, tzinfo=timezone.utc),
            )

        # Exact date: YYYY-MM-DD
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", expr):
            try:
                day = datetime.strptime(expr, "%Y-%m-%d").date()
            except ValueError:
                raise TimeResolutionError(f"Invalid date: '{expr}'")
            return TimeWindow(
                start=datetime.combine(day, DAY_START, tzinfo=timezone.utc),
                end=datetime.combine(day, DAY_END, tzinfo=timezone.utc),
            )

        raise TimeResolutionError(f"Unknown time expression: '{expr}'")

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _default_window(self) -> TimeWindow:
        """Default fallback — last 7 days from now in UTC."""
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=7)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return TimeWindow(start=start, end=now)

    @staticmethod
    def _clamp_date(target_date: date, min_date: date, max_date: date) -> date:
        """Clamp a date to the available data range."""
        if target_date < min_date:
            return min_date
        if target_date > max_date:
            return max_date
        return target_date

    def _apply_fallback(self, window: TimeWindow, message: str) -> dict:
        """Build a fallback response dict from a window and message."""
        return {
            "requested": window.to_dict(),
            "actual": window.to_dict(),
            "fallback_triggered": True,
            "message": message,
        }

    @staticmethod
    def _generate_message(
        expr: str,
        target_start: date,
        target_end: date,
        actual_start: date,
        actual_end: date,
        min_date: date,
        max_date: date,
    ) -> str:
        """Generate a human-readable fallback explanation for the LLM."""
        if target_start == target_end:
            if target_start > max_date:
                return (
                    f"No data available for {expr} ({target_start}). "
                    f"The most recent data is from {max_date}. "
                    f"Showing results from that date instead."
                )
            return (
                f"No data available for {expr} ({target_start}). "
                f"The earliest data is from {min_date}. "
                f"Showing results from that date instead."
            )

        return (
            f"No data available for '{expr}' ({target_start} to {target_end}). "
            f"Available data spans {min_date} to {max_date}. "
            f"Showing results from {actual_start} to {actual_end} instead."
        )