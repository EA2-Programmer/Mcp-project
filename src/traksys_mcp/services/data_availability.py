"""
Data availability caching for intelligent time resolution.

Caches min/max dates per table to enable fallback when user requests
dates outside the available data range.
"""

from traksys_mcp.core.database import execute_query
from typing import Optional, Tuple
from datetime import date
import logging

logger = logging.getLogger(__name__)


class DataAvailabilityCache:
    """
    Caches min/max dates per table to enable intelligent fallback.

    When user asks for "yesterday" but data is from 2024, this cache
    lets TimeResolutionService know what dates actually exist.
    """

    def __init__(self):
        self._cache: dict[str, Tuple[date, date]] = {}

    async def get_range(self, table: str) -> Optional[Tuple[date, date]]:
        """
        Get the min/max date range for a table.

        Args:
            table: Table name (e.g., 'tBatch', 'tJobSystemActual')

        Returns:
            (min_date, max_date) tuple or None if no data
        """
        if table in self._cache:
            return self._cache[table]

        # Query database for range
        await self.refresh(table)
        return self._cache.get(table)

    async def refresh(self, table: str) -> None:
        """
        Refresh the date range for a specific table.

        Queries the database for MIN/MAX of the timestamp column.
        """
        timestamp_column = self._get_timestamp_column(table)

        if not timestamp_column:
            logger.warning(f"No timestamp column mapped for table {table}")
            return

        sql = f"""
            SELECT 
                MIN(CAST({timestamp_column} AS DATE)) AS MinDate,
                MAX(CAST({timestamp_column} AS DATE)) AS MaxDate
            FROM {table}
            WHERE {timestamp_column} IS NOT NULL
        """

        try:
            columns, rows = await execute_query(sql, ())

            if rows and rows[0][0] and rows[0][1]:
                min_date = rows[0][0]
                max_date = rows[0][1]
                self._cache[table] = (min_date, max_date)
                logger.info(f"Cached date range for {table}: {min_date} to {max_date}")
            else:
                logger.warning(f"No data found in {table}")

        except Exception as e:
            logger.error(f"Failed to refresh cache for {table}: {e}")

    async def refresh_all(self) -> None:
        """Refresh cache for all known tables."""
        tables = [
            'tBatch',
            'tJobSystemActual',
            'tMaterialUseActual',
            'tBatchParameter'
        ]

        for table in tables:
            await self.refresh(table)

    @staticmethod
    def _get_timestamp_column(table: str) -> Optional[str]:
        """
        Map table names to their primary timestamp columns.

        Based on your actual schema.
        """
        mapping = {
            'tBatch': 'StartDateTime',
            'tJobSystemActual': 'StartDateTime',
            'tMaterialUseActual': 'DateTime',
            'tBatchParameter': 'ModifiedDateTime',
        }
        return mapping.get(table)