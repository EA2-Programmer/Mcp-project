from datetime import datetime, timedelta
import re
from typing import Optional


class TimeResolutionError(Exception):
    """Raised when time expression cannot be parsed."""
    pass


class TimeWindow:
    def __init__(self, start: datetime, end: datetime):
        self.start = start
        self.end = end

    def to_dict(self):
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat()
        }


class TimeResolutionService:
    """Converts natural language to time windows with intelligent fallback."""

    def __init__(self, data_cache):
        self.cache = data_cache

    async def resolve(self, expression: str, table: str = "tBatch") -> dict:
        """
        Parse time expression and return window with fallback info.

        Returns:
        {
            "requested": {"start": "...", "end": "..."},
            "actual": {"start": "...", "end": "..."},
            "fallback_triggered": bool,
            "message": Optional[str]
        }
        """
        # Step 1: Parse expression to target window
        try:
            target = self._parse_expression(expression)
        except TimeResolutionError:
            # Default to last 7 days if can't parse
            target = self._default_window()
            fallback_msg = f"Could not understand '{expression}'. Using last 7 days."
            return self._apply_fallback(target, fallback_msg)

        # Step 2: Check if target exists in database
        available = await self.cache.get_range(table)
        if not available:
            return {
                "requested": self._window_to_dict(target),
                "actual": self._window_to_dict(target),
                "fallback_triggered": False,
                "message": None
            }

        min_date, max_date = available

        # Step 3: Check if target dates exist
        target_start_date = target.start.date()
        target_end_date = target.end.date()

        if min_date <= target_start_date <= max_date and min_date <= target_end_date <= max_date:
            # Perfect match - no fallback
            return {
                "requested": self._window_to_dict(target),
                "actual": self._window_to_dict(target),
                "fallback_triggered": False,
                "message": None
            }

        # Step 4: Fallback needed
        actual_start = self._clamp_date(target_start_date, min_date, max_date)
        actual_end = self._clamp_date(target_end_date, min_date, max_date)

        actual_window = TimeWindow(
            start=datetime.combine(actual_start, datetime.min.time()),
            end=datetime.combine(actual_end, datetime.max.time())
        )

        message = self._generate_message(expression, target_start_date, target_end_date,
                                         actual_start, actual_end, min_date, max_date)

        return {
            "requested": self._window_to_dict(target),
            "actual": self._window_to_dict(actual_window),
            "fallback_triggered": True,
            "message": message
        }

    def _parse_expression(self, expr: str) -> TimeWindow:
        """Parse natural language expressions."""
        expr = expr.lower().strip()
        now = datetime.now()

        # Yesterday
        if expr == "yesterday":
            day = (now - timedelta(days=1)).date()
            return TimeWindow(
                start=datetime.combine(day, datetime.min.time()),
                end=datetime.combine(day, datetime.max.time())
            )

        # Last X days
        match = re.match(r"last (\d+) days?", expr)
        if match:
            days = int(match.group(1))
            start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0)
            return TimeWindow(start=start, end=now)

        # This week
        if expr == "this week":
            start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)
            end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
            return TimeWindow(start=start, end=end)

        # Exact date: 2024-08-31
        if re.match(r"\d{4}-\d{2}-\d{2}", expr):
            day = datetime.strptime(expr, "%Y-%m-%d").date()
            return TimeWindow(
                start=datetime.combine(day, datetime.min.time()),
                end=datetime.combine(day, datetime.max.time())
            )

        raise TimeResolutionError(f"Unknown expression: {expr}")

    def _default_window(self) -> TimeWindow:
        """Default to last 7 days."""
        now = datetime.now()
        start = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0)
        return TimeWindow(start=start, end=now)

    def _clamp_date(self, target_date, min_date, max_date):
        """Clamp date to available range."""
        if target_date < min_date:
            return min_date
        if target_date > max_date:
            return max_date
        return target_date

    def _window_to_dict(self, window: TimeWindow) -> dict:
        return {
            "start": window.start.isoformat(),
            "end": window.end.isoformat()
        }

    @staticmethod
    def _generate_message(expr, target_start, target_end,
                          actual_start, actual_end, min_date, max_date) -> str:
        """Generate user-friendly fallback message."""
        if target_start == target_end:  # Single day
            if target_start > max_date:
                return (
                    f"No data available for {expr} ({target_start}). "
                    f"The most recent data is from {max_date}. "
                    f"Showing results from that date instead."
                )
            else:
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