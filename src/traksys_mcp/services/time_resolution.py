"""
Time resolution service with fallback.

Converts natural language time expressions to datetime windows,
checking against available data and clamping when necessary.

Dependencies:
    pip install dateparser python-dateutil
"""

from calendar import monthrange
from datetime import datetime, date, time, timezone, timedelta
import logging
from typing import TYPE_CHECKING

from src.traksys_mcp.core.exceptions import TrakSYSError

if TYPE_CHECKING:
    from data_availability import DataAvailabilityCache

logger = logging.getLogger(__name__)

DAY_START = time(0, 0, 0)
DAY_END   = time(23, 59, 59, 999999)

# dateparser settings — always interpret relative to now, always UTC
_DATEPARSER_SETTINGS = {
    "RETURN_TIME_AS_PERIOD": False,
    "PREFER_DAY_OF_MONTH": "first",
    "PREFER_DATES_FROM": "past",
    "TIMEZONE": "UTC",
    "RETURN_AS_TIMEZONE_AWARE": True,
    "TO_TIMEZONE": "UTC",
}


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

    Uses `dateparser` for broad natural language support, with a thin
    layer on top to handle period expressions ("September 2025",
    "last month") that need a start AND end, not just a single point.

    Checks the resolved window against available data in the database
    and clamps to the actual range when needed.
    """

    def __init__(self, data_cache: "DataAvailabilityCache"):
        self.cache = data_cache

    async def resolve(self, expression: str, table: str = "tBatch") -> dict:
        """
        Parse time expression and return window with fallback info.

        Returns:
            {
                "requested":        {"start": "...", "end": "..."},
                "actual":           {"start": "...", "end": "..."},
                "fallback_triggered": bool,
                "message":          str | None
            }
        """
        try:
            target = self._parse_expression(expression)
        except TimeResolutionError as e:
            logger.warning("Time expression parse failed: '%s' → %s", expression, e)
            target = self._default_window()
            return self._apply_fallback(
                target,
                f"Could not understand '{expression}'. Using last 7 days instead."
            )

        available = await self.cache.get_range(table)
        if not available:
            return {
                "requested": target.to_dict(),
                "actual":    target.to_dict(),
                "fallback_triggered": False,
                "message": None,
            }

        min_date, max_date = available
        target_start_date = target.start.date()
        target_end_date   = target.end.date()

        if (min_date <= target_start_date <= max_date and
                min_date <= target_end_date   <= max_date):
            return {
                "requested": target.to_dict(),
                "actual":    target.to_dict(),
                "fallback_triggered": False,
                "message": None,
            }

        actual_start = self._clamp_date(target_start_date, min_date, max_date)
        actual_end   = self._clamp_date(target_end_date,   min_date, max_date)

        actual_window = TimeWindow(
            start=datetime.combine(actual_start, DAY_START, tzinfo=timezone.utc),
            end=  datetime.combine(actual_end,   DAY_END,   tzinfo=timezone.utc),
        )

        return {
            "requested": target.to_dict(),
            "actual":    actual_window.to_dict(),
            "fallback_triggered": True,
            "message": self._generate_message(
                expression,
                target_start_date, target_end_date,
                actual_start, actual_end,
                min_date, max_date,
            ),
        }

    # -----------------------------------------------------------------------
    # Parsing
    # -----------------------------------------------------------------------

    def _parse_expression(self, expr: str) -> TimeWindow:
        """
        Parse any natural language time expression into a TimeWindow.

        Strategy (in order):
          1. Period expressions ("September 2025", "last month", "this week",
             "Q3 2025") — need a start AND end date, handled explicitly.
          2. dateparser.parse() — handles everything else: "yesterday",
             "2 weeks ago", "2025-09-01", "last 7 days", etc.
        """
        try:
            import dateparser
            from dateparser.search import search_dates
        except ImportError:
            raise TimeResolutionError(
                "dateparser not installed. Run: pip install dateparser"
            )

        expr_stripped = expr.strip()
        lower = expr_stripped.lower()
        now = datetime.now(timezone.utc)

        # ── 1. Period expressions that need start + end ────────────────────

        # "this week" → Monday to Sunday of current week
        if lower == "this week":
            start = (now - timedelta(days=now.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end = (start + timedelta(days=6)).replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
            return TimeWindow(start=start, end=end)

        # "last week" → previous full Mon–Sun
        if lower == "last week":
            start_of_this_week = (now - timedelta(days=now.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            start = start_of_this_week - timedelta(days=7)
            end   = (start_of_this_week - timedelta(seconds=1)).replace(
                microsecond=999999
            )
            return TimeWindow(start=start, end=end)

        # "this month"
        if lower == "this month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_day = monthrange(now.year, now.month)[1]
            end = now.replace(
                day=last_day, hour=23, minute=59, second=59, microsecond=999999
            )
            return TimeWindow(start=start, end=end)

        # "last month"
        if lower == "last month":
            first_of_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_of_prev  = first_of_this - timedelta(seconds=1)
            first_of_prev = last_of_prev.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            return TimeWindow(start=first_of_prev, end=last_of_prev)

        # "Month YYYY" or "Month, YYYY" — e.g. "September 2025", "Sep 2025"
        # dateparser parses this as a single point (first of month);
        # we need the full month range.
        month_year = dateparser.parse(
            expr_stripped,
            settings={**_DATEPARSER_SETTINGS, "PREFER_DAY_OF_MONTH": "first"},
        )
        if month_year:
            # Check if dateparser thinks the period is "month"
            from dateparser.date import DateDataParser
            ddp = DateDataParser(settings=_DATEPARSER_SETTINGS)
            data = ddp.get_date_data(expr_stripped)
            if data and data.get("period") == "month":
                d = data["date_obj"].astimezone(timezone.utc)
                last_day = monthrange(d.year, d.month)[1]
                return TimeWindow(
                    start=d.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                    end=  d.replace(day=last_day, hour=23, minute=59,
                                    second=59, microsecond=999999),
                )
            if data and data.get("period") == "year":
                d = data["date_obj"].astimezone(timezone.utc)
                return TimeWindow(
                    start=d.replace(month=1, day=1, hour=0, minute=0,
                                    second=0, microsecond=0),
                    end=  d.replace(month=12, day=31, hour=23, minute=59,
                                    second=59, microsecond=999999),
                )

        # ── 2. dateparser handles everything else ──────────────────────────
        # "yesterday", "last 7 days", "2025-09-01", "2 weeks ago", etc.
        parsed = dateparser.parse(expr_stripped, settings=_DATEPARSER_SETTINGS)
        if parsed:
            day = parsed.astimezone(timezone.utc).date()
            return TimeWindow(
                start=datetime.combine(day, DAY_START, tzinfo=timezone.utc),
                end=  datetime.combine(day, DAY_END,   tzinfo=timezone.utc),
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
        if target_date < min_date:
            return min_date
        if target_date > max_date:
            return max_date
        return target_date

    def _apply_fallback(self, window: TimeWindow, message: str) -> dict:
        return {
            "requested": window.to_dict(),
            "actual":    window.to_dict(),
            "fallback_triggered": True,
            "message": message,
        }

    @staticmethod
    def _generate_message(
        expr: str,
        target_start: date, target_end: date,
        actual_start: date, actual_end: date,
        min_date: date, max_date: date,
    ) -> str:
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