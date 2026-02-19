"""
Health check utilities for monitoring server status.

Provides functions for:
- Liveness probes (is the server running?)
- Readiness probes (is the server ready to handle requests?)
"""

from src.traksys_mcp.core.database import check_connection
from typing import Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


async def health_check() -> Dict[str, Any]:
    """
    Liveness probe - check if server is running.

    This is a simple check that the server process is alive.
    It does NOT check external dependencies.

    Returns:
        Health status dict with timestamp
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "server": "TrakSYS MCP",
        "version": "1.0.0"
    }


async def readiness_check() -> Dict[str, Any]:
    """
    Readiness probe - check if server can handle requests.

    This checks that all dependencies (database, etc.) are available.
    Use this to determine if the server should receive traffic.

    Returns:
        Readiness status dict with dependency checks
    """
    is_db_ready = await check_connection()
    is_ready = is_db_ready  # Can add more checks here later

    return {
        "status": "ready" if is_ready else "not_ready",
        "checks": {
            "database": "connected" if is_db_ready else "disconnected"
        },
        "timestamp": datetime.utcnow().isoformat(),
    }