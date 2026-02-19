"""
Entry point for running the TrakSYS MCP server.

Usage:
    python -m traksys_mcp
"""

import asyncio
from src.traksys_mcp.server import main

if __name__ == "__main__":
    asyncio.run(main())