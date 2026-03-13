import logging
from datetime import date
from typing import Optional, Tuple

from src.traksys_mcp.core.database import execute_query

logger = logging.getLogger(__name__)

_TIMESTAMP_COLUMNS: dict[str, str] = {
    "tBatch": "StartDateTime",
    "tJobSystemActual": "StartDateTime",
    "tMaterialUseActual": "DateTime",
    "tBatchParameter": "ModifiedDateTime",
}


class DataAvailabilityCache:
    """
    Caches min/max dates per table to enable intelligent time fallback.

    When a user asks for "yesterday" but data is from 2024, this cache
    lets TimeResolutionService know what dates actually exist so it can
    clamp the window instead of returning empty results.
    """

    def __init__(self):
        self._cache: dict[str, Tuple[date, date]] = {}

    async def get_range(self, table: str) -> Optional[Tuple[date, date]]:
        if table not in self._cache:
            await self.refresh(table)
        return self._cache.get(table)

    async def refresh(self, table: str) -> None:
        timestamp_column = _TIMESTAMP_COLUMNS.get(table)
        if not timestamp_column:
            logger.warning("No timestamp column mapped for table %s", table)
            return

        sql = f"""
            SELECT
                MIN(CAST({timestamp_column} AS DATE)) AS MinDate,
                MAX(CAST({timestamp_column} AS DATE)) AS MaxDate
            FROM {table}
            WHERE {timestamp_column} IS NOT NULL
        """
        try:
            _, rows = await execute_query(sql, ())
            if rows and rows[0][0] and rows[0][1]:
                self._cache[table] = (rows[0][0], rows[0][1])
                logger.info("Cached date range for %s: %s to %s", table, rows[0][0], rows[0][1])
            else:
                logger.warning("No data found in %s", table)
        except Exception as e:
            logger.error("Failed to refresh cache for %s: %s", table, e)

    async def refresh_all(self) -> None:
        for table in _TIMESTAMP_COLUMNS:
            await self.refresh(table)