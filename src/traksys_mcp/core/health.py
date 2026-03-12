from datetime import datetime, timezone
from typing import Any

import logging

from src.traksys_mcp.core.database import check_connection

logger = logging.getLogger(__name__)


async def health_check() -> dict[str, Any]:
    """Liveness probe — confirms the server process is alive, no external checks."""
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "server": "TrakSYS MCP",
        "version": "1.0.0",
    }


async def readiness_check() -> dict[str, Any]:
    """Readiness probe — confirms all dependencies (database) are reachable."""
    is_db_ready = await check_connection()
    return {
        "status": "ready" if is_db_ready else "not_ready",
        "checks": {
            "database": "connected" if is_db_ready else "disconnected"
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }