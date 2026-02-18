"""
TrakSYS MCP Server bootstrap and lifecycle management.

Class-based architecture with proper dependency injection.
"""

import asyncio
import logging
from typing import Optional

from fastmcp import FastMCP

from traksys_mcp.config.setting import settings
from traksys_mcp.config.logging_setup import setup_logging
from traksys_mcp.core.database import check_connection
from traksys_mcp.core.exceptions import ConnectionsError
from traksys_mcp.services.data_availability import DataAvailabilityCache
from traksys_mcp.services.time_resolution import TimeResolutionService
from traksys_mcp.tools.batches import BatchTools


class TrakSYSMCPServer:
    """
    Main MCP server class.

    Handles initialization, dependency injection, and lifecycle management.
    """

    def __init__(self):
        """Initialize server with empty state."""
        self.logger = logging.getLogger(__name__)
        self.mcp: Optional[FastMCP] = None

        # Services (injected after async initialization)
        self.data_cache: Optional[DataAvailabilityCache] = None
        self.time_service: Optional[TimeResolutionService] = None

        # Tools (registered after services are ready)
        self.batch_tools: Optional[BatchTools] = None

    def setup_logging(self) -> None:
        """Initialize logging configuration."""
        setup_logging()
        self.logger.info("=" * 60)
        self.logger.info("TrakSYS MCP Server v1.0.0")
        self.logger.info("=" * 60)

    async def initialize(self) -> None:
        """
        Async initialization of services and dependencies.

        This runs BEFORE tools are registered.
        """
        self.logger.info("Initializing TrakSYS services...")

        # Check database connectivity
        self.logger.info("Checking database connection...")
        if not await check_connection():
            raise ConnectionsError(
                "Cannot reach database. Check MSSQL_CONNECTION_STRING in .env"
            )
        self.logger.info("✓ Database connection verified")

        # Initialize data availability cache
        self.logger.info("Initializing data availability cache...")
        self.data_cache = DataAvailabilityCache()
        await self.data_cache.refresh_all()
        self.logger.info("✓ Data cache ready")

        # Initialize time resolution service (depends on cache)
        self.time_service = TimeResolutionService(self.data_cache)
        self.logger.info("✓ Time resolution service ready")

        self.logger.info("All services initialized successfully")

    def register_tools(self) -> None:
        """
        Register all MCP tools with the FastMCP instance.

        Uses composition - each tool domain is a separate class.
        """
        self.logger.info("Registering MCP tools...")

        # Create FastMCP instance
        self.mcp = FastMCP("TrakSYS Manufacturing Analytics")

        # Register batch tools
        self.batch_tools = BatchTools(
            mcp=self.mcp,
            time_service=self.time_service
        )
        self.batch_tools.register()

        # Add more tool registrations as they're built:
        # self.material_tools = MaterialTools(mcp=self.mcp, time_service=self.time_service)
        # self.material_tools.register()

        # self.quality_tools = QualityTools(mcp=self.mcp, time_service=self.time_service)
        # self.quality_tools.register()

        # self.performance_tools = PerformanceTools(mcp=self.mcp, time_service=self.time_service)
        # self.performance_tools.register()

        self.logger.info("✓ Tools registered")

    async def run(self) -> None:
        """
        Run the MCP server.

        Lifecycle:
        1. Setup logging
        2. Initialize services (async)
        3. Register tools
        4. Start transport (stdio or HTTP)
        """
        # Setup
        self.setup_logging()

        # Initialize services
        await self.initialize()

        # Register tools
        self.register_tools()

        # Log configuration
        self.logger.info("=" * 60)
        self.logger.info("Configuration:")
        self.logger.info("  Transport: %s", settings.SERVER_TRANSPORT)
        self.logger.info("  Read-only: %s", settings.READ_ONLY)
        self.logger.info("  Max rows: %d", settings.MAX_ROWS)
        self.logger.info("=" * 60)

        # Start server based on transport
        if settings.SERVER_TRANSPORT == "stdio":
            await self._run_stdio()
        elif settings.SERVER_TRANSPORT == "http":
            await self._run_http()
        else:
            raise ValueError(f"Unknown transport: {settings.SERVER_TRANSPORT}")

    async def _run_stdio(self) -> None:
        """Run server with STDIO transport."""
        self.logger.info("Starting MCP server with STDIO transport")
        self.logger.info("Server is ready and waiting for requests...")

        # FastMCP handles the async stdio loop
        await self.mcp.run_stdio_async()

    async def _run_http(self) -> None:
        """Run server with HTTP transport."""
        self.logger.info(
            "Starting MCP server with HTTP transport on %s:%d",
            settings.HTTP_BIND_HOST,
            settings.HTTP_BIND_PORT
        )

        # Configure FastMCP for HTTP
        self.mcp.settings.host = settings.HTTP_BIND_HOST
        self.mcp.settings.port = settings.HTTP_BIND_PORT

        # FastMCP handles the HTTP server (uvicorn + Starlette)
        await self.mcp.run_http_async()


def create_server() -> TrakSYSMCPServer:
    """
    Factory function to create the MCP server.

    Returns:
        Configured TrakSYSMCPServer instance
    """
    return TrakSYSMCPServer()


async def main() -> None:
    """Main entry point for the server."""
    server = create_server()

    try:
        await server.run()
    except KeyboardInterrupt:
        logging.info("Server interrupted by user")
    except Exception as e:
        logging.exception("Server error: %s", e)
        raise


if __name__ == "__main__":
    asyncio.run(main())