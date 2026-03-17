"""
Time resolution service for parsing natural/semi-structured time expressions.
FEEL FREE KINGSLEY AND HUDINI TO CHANEG THIS CLAS SIF IT DOESN4T WORK WELL FOR U
Converts expressions like "last month", "March 2025", "2025-09", "this quarter"
into timezone-aware datetime windows (UTC), with fallback and data availability clamping.
"""

from calendar import monthrange, month_name, month_abbr
from datetime import datetime, date, time, timezone, timedelta
import re
import logging
from typing import TYPE_CHECKING

from src.traksys_mcp.core.exceptions import TrakSYSError

if TYPE_CHECKING:
    from data_availability import DataAvailabilityCache

logger = logging.getLogger(__name__)

# Module-level constants
DAY_START = time(0, 0)
DAY_END = time(23, 59, 59, 999_999)

# Month name → number mapping (full + abbreviated, case-insensitive)
MONTH_NAME_TO_NUM = {
    **{name.lower(): i for i, name in enumerate(month_name[1:], 1)},
    **{name.lower(): i for i, name in enumerate(month_abbr[1:], 1)},
}

QUARTER_START_MONTH = {1: 1, 2: 4, 3: 7, 4: 10}


class TimeResolutionError(TrakSYSError):
    """Raised when a time expression cannot be parsed or is invalid."""
    pass


class TimeWindow:
    """Immutable timezone-aware time range."""

    def __init__(self, start: datetime, end: datetime):
        if start > end:
            raise ValueError("Start datetime must not be after end")
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("Both datetimes must be timezone-aware")
        self.start = start
        self.end = end

    def to_dict(self) -> dict[str, str]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
        }

    def __repr__(self) -> str:
        return f"TimeWindow({self.start.isoformat()} → {self.end.isoformat()})"


class TimeResolutionService:
    """
    Parses time expressions into UTC TimeWindow objects and clamps them
    against available data ranges when necessary.

    Returns structured responses suitable for API / LLM / user feedback.
    """

    def __init__(self, data_cache: "DataAvailabilityCache"):
        self.cache = data_cache

    async def resolve(
        self,
        expression: str,
        table: str = "tBatch"
    ) -> dict[str, object]:
        """
        Parse expression → TimeWindow, clamp if needed, return structured result.

        Returns:
            {
                "requested": {"start": iso, "end": iso},
                "actual":    {"start": iso, "end": iso},
                "fallback_triggered": bool,
                "message": str | None
            }
        """
        expr = expression.strip()
        if not expr:
            raise TimeResolutionError("Empty time expression")

        try:
            target_window = self._parse_expression(expr)
        except TimeResolutionError as exc:
            logger.warning("Failed to parse time expression %r: %s", expr, exc)
            target_window = self._get_default_window()
            return self._build_fallback_response(
                target_window,
                f"Could not understand '{expr}'. Showing last 7 days instead."
            )

        available_range = await self.cache.get_range(table)
        if not available_range:
            return {
                "requested": target_window.to_dict(),
                "actual": target_window.to_dict(),
                "fallback_triggered": False,
                "message": None,
            }

        min_date, max_date = available_range
        req_start_date = target_window.start.date()
        req_end_date = target_window.end.date()

        if min_date <= req_start_date <= max_date and min_date <= req_end_date <= max_date:
            return {
                "requested": target_window.to_dict(),
                "actual": target_window.to_dict(),
                "fallback_triggered": False,
                "message": None,
            }

        actual_start_date = self._clamp_date(req_start_date, min_date, max_date)
        actual_end_date = self._clamp_date(req_end_date, min_date, max_date)

        actual_window = TimeWindow(
            start=datetime.combine(actual_start_date, DAY_START, tzinfo=timezone.utc),
            end=datetime.combine(actual_end_date, DAY_END, tzinfo=timezone.utc),
        )

        return {
            "requested": target_window.to_dict(),
            "actual": actual_window.to_dict(),
            "fallback_triggered": True,
            "message": self._build_clamp_message(
                expr,
                req_start_date,
                req_end_date,
                actual_start_date,
                actual_end_date,
                min_date,
                max_date,
            ),
        }

    # -------------------------------------------------------------------------
    # Parsing core
    # -------------------------------------------------------------------------

    def _parse_expression(self, expr: str) -> TimeWindow:
        lower = expr.lower().strip()
        now = datetime.now(timezone.utc)

        # Quick literals
        if lower in {"today", "now"}:
            return self._full_day(now.date())

        if lower == "yesterday":
            return self._full_day((now - timedelta(days=1)).date())

        # Last N <unit>
        if m := re.match(r"last\s+(\d+)\s*(day|days|week|weeks|month|months|year|years)\b", lower):
            count = int(m.group(1))
            unit = m.group(2).rstrip("s")
            if unit == "day":
                start = now - timedelta(days=count)
            elif unit == "week":
                start = now - timedelta(weeks=count)
            elif unit == "month":
                start = self._subtract_months(now, count)
            elif unit == "year":
                start = now.replace(year=now.year - count)
            else:
                raise TimeResolutionError(f"Unsupported unit: {unit}")
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            return TimeWindow(start=start, end=now)

        # This / last month / year / quarter
        if lower in {"this month", "current month"}:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return TimeWindow(start=start, end=now)

        if lower == "last month":
            prev = self._subtract_months(now, 1)
            start = prev.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = prev.replace(
                day=monthrange(prev.year, prev.month)[1],
                hour=23, minute=59, second=59, microsecond=999_999
            )
            return TimeWindow(start=start, end=end)

        if lower in {"this year", "current year"}:
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            return TimeWindow(start=start, end=now)

        if lower == "last year":
            year = now.year - 1
            start = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
            end = datetime(year, 12, 31, 23, 59, 59, 999_999, tzinfo=timezone.utc)
            return TimeWindow(start=start, end=end)

        # Quarter
        if m := re.match(r"(this|last)\s*quarter\b", lower):
            current_q = (now.month - 1) // 3 + 1
            year = now.year
            q = current_q if m.group(1) == "this" else current_q - 1
            if q == 0:
                q = 4
                year -= 1
            start_month = QUARTER_START_MONTH[q]
            start = datetime(year, start_month, 1, 0, 0, 0, tzinfo=timezone.utc)
            end_month = start_month + 2
            end = datetime(
                year, end_month, monthrange(year, end_month)[1],
                23, 59, 59, 999_999, tzinfo=timezone.utc
            )
            return TimeWindow(start=start, end=end)

        if m := re.match(r"q([1-4])\s*(\d{4})", lower):
            q, year = int(m.group(1)), int(m.group(2))
            start_month = QUARTER_START_MONTH[q]
            start = datetime(year, start_month, 1, 0, 0, 0, tzinfo=timezone.utc)
            end_month = start_month + 2
            end = datetime(
                year, end_month, monthrange(year, end_month)[1],
                23, 59, 59, 999_999, tzinfo=timezone.utc
            )
            return TimeWindow(start=start, end=end)

        # Named month + year
        if m := re.match(r"([a-z]+)\s*,?\s*(\d{4})\b", lower):
            month_str, year_str = m.groups()
            month = MONTH_NAME_TO_NUM.get(month_str)
            if month:
                year = int(year_str)
                start = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
                end = datetime(
                    year, month, monthrange(year, month)[1],
                    23, 59, 59, 999_999, tzinfo=timezone.utc
                )
                return TimeWindow(start=start, end=end)

        # ISO year-month
        if m := re.fullmatch(r"(\d{4})-(\d{2})", lower):
            year, month = int(m.group(1)), int(m.group(2))
            if 1 <= month <= 12:
                start = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
                end = datetime(
                    year, month, monthrange(year, month)[1],
                    23, 59, 59, 999_999, tzinfo=timezone.utc
                )
                return TimeWindow(start=start, end=end)

        # Explicit range
        if m := re.match(r"(\d{4}-\d{2}-\d{2})\s*(?:to|-)\s*(\d{4}-\d{2}-\d{2})", lower):
            try:
                s = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                e = datetime.strptime(m.group(2), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                return TimeWindow(
                    start=s.replace(hour=0, minute=0, second=0, microsecond=0),
                    end=e.replace(hour=23, minute=59, second=59, microsecond=999_999)
                )
            except ValueError:
                raise TimeResolutionError(f"Invalid date range format: {expr}")

        # Single ISO date
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", lower):
            try:
                dt = datetime.strptime(lower, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                return self._full_day(dt.date())
            except ValueError:
                raise TimeResolutionError(f"Invalid date format: {expr}")

        raise TimeResolutionError(f"Unsupported time expression: '{expr}'")

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _full_day(self, d: date) -> TimeWindow:
        return TimeWindow(
            start=datetime.combine(d, DAY_START, tzinfo=timezone.utc),
            end=datetime.combine(d, DAY_END, tzinfo=timezone.utc),
        )

    @staticmethod
    def _subtract_months(dt: datetime, months: int) -> datetime:
        """Subtract months while preserving as much of the day as possible."""
        year = dt.year
        month = dt.month - months
        while month <= 0:
            month += 12
            year -= 1
        day = min(dt.day, monthrange(year, month)[1])
        return dt.replace(year=year, month=month, day=day)

    def _get_default_window(self) -> TimeWindow:
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=7)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return TimeWindow(start=start, end=now)

    @staticmethod
    def _clamp_date(target: date, min_date: date, max_date: date) -> date:
        return max(min_date, min(target, max_date))

    def _build_fallback_response(self, window: TimeWindow, message: str) -> dict:
        return {
            "requested": window.to_dict(),
            "actual": window.to_dict(),
            "fallback_triggered": True,
            "message": message,
        }

    @staticmethod
    def _build_clamp_message(
        expr: str,
        req_start: date,
        req_end: date,
        act_start: date,
        act_end: date,
        min_d: date,
        max_d: date,
    ) -> str:
        if req_start == req_end:
            if req_start > max_d:
                return f"No data for '{expr}' ({req_start}). Latest: {max_d}. Showing {act_start}."
            return f"No data for '{expr}' ({req_start}). Earliest: {min_d}. Showing {act_start}."

        return (
            f"Requested '{expr}' ({req_start} – {req_end}) "
            f"outside available range ({min_d} – {max_d}). "
            f"Showing {act_start} – {act_end} instead."
        )