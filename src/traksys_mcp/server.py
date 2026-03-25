import asyncio
import logging
from typing import Optional

from fastmcp import FastMCP

from src.traksys_mcp.config.setting import settings
from src.traksys_mcp.config.logging_setup import setup_logging
from src.traksys_mcp.core.database import check_connection
from src.traksys_mcp.core.exceptions import DatabaseConnectionError
from src.traksys_mcp.services.data_availability import DataAvailabilityCache
from src.traksys_mcp.services.time_resolution import TimeResolutionService
from src.traksys_mcp.services.langfuse_tracing import TracingService, register_instance
from src.traksys_mcp.tools.batches import BatchTools
from src.traksys_mcp.tools.performance import PerformanceTools
from src.traksys_mcp.tools.meta import MetaTools
from src.traksys_mcp.tools.product import RecipeTools
from src.traksys_mcp.tools.tasks import TaskTools
from src.traksys_mcp.tools.Analysis import AnalysisTools
from src.traksys_mcp.tools.materials import MaterialsTools


class TrakSYSMCPServer:
    """Main server class — owns service lifecycle and tool registration."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.mcp: Optional[FastMCP] = None
        self.data_cache: Optional[DataAvailabilityCache] = None
        self.time_service: Optional[TimeResolutionService] = None
        self.tracing: Optional[TracingService] = None
        self.batch_tools: Optional[BatchTools] = None
        self.performance_tools: Optional[PerformanceTools] = None
        self.meta_tools: Optional[MetaTools] = None
        self.task_tools: Optional[TaskTools] = None
        self.oee_tools: Optional[AnalysisTools] = None
        self.materials_tools: Optional[MaterialsTools] = None
        self.recipe_tools: Optional[RecipeTools] = None

    def _setup_logging(self) -> None:
        setup_logging()
        self.logger.info("=" * 60)
        self.logger.info("TrakSYS MCP Server v1.0.0")
        self.logger.info("=" * 60)

    async def initialize(self) -> None:
        """Async service initialization."""
        self.logger.info("Initializing TrakSYS services...")

        self.tracing = TracingService()
        register_instance(self.tracing)
        self.logger.info("✓ Tracing service ready (enabled=%s)", self.tracing.enabled)

        if not await check_connection():
            raise DatabaseConnectionError(
                "Cannot reach database. Check MSSQL_CONNECTION_STRING in .env"
            )
        self.logger.info("✓ Database connection verified")

        # === Key fix: background cache refresh so startup is fast ===
        self.data_cache = DataAvailabilityCache()
        asyncio.create_task(self._refresh_cache_background())

        self.time_service = TimeResolutionService(self.data_cache)
        self.logger.info("✓ Time resolution service ready (cache refresh started in background)")

        self.logger.info("All core services initialized successfully")

    async def _refresh_cache_background(self) -> None:
        """Refresh date cache without blocking MCP handshake."""
        try:
            self.logger.info("Starting background cache refresh...")
            await self.data_cache.refresh_all()
            self.logger.info("✓ Background cache refresh completed")
        except Exception as e:
            self.logger.error("Background cache refresh failed: %s", e)

    def register_tools(self) -> None:
        self.mcp = FastMCP("TrakSYS Manufacturing Analytics")

        self.batch_tools = BatchTools(mcp=self.mcp, time_service=self.time_service, tracing=self.tracing)
        self.batch_tools.register()

        self.performance_tools = PerformanceTools(mcp=self.mcp, tracing=self.tracing)
        self.performance_tools.register()

        self.meta_tools = MetaTools(mcp=self.mcp, tracing=self.tracing)
        self.meta_tools.register()

        self.task_tools = TaskTools(mcp=self.mcp, time_service=self.time_service, tracing=self.tracing)
        self.task_tools.register()

        self.oee_tools = AnalysisTools(mcp=self.mcp, time_service=self.time_service)
        self.oee_tools.register()

        self.materials_tools = MaterialsTools(mcp=self.mcp, time_service=self.time_service)
        self.materials_tools.register()

        self.recipe_tools = RecipeTools(mcp=self.mcp, tracing=self.tracing)
        self.recipe_tools.register()

        self.logger.info("Tools registered")

    async def run(self) -> None:
        self._setup_logging()
        try:
            await self.initialize()
            self.register_tools()

            self.logger.info("=" * 60)
            self.logger.info("Configuration:")
            self.logger.info("  Transport: %s", settings.SERVER_TRANSPORT)
            self.logger.info("  Read-only: %s", settings.READ_ONLY)
            self.logger.info("  Max rows:  %d", settings.MAX_ROWS)
            self.logger.info("  Tracing:   %s", self.tracing.enabled if self.tracing else False)
            self.logger.info("=" * 60)

            if settings.SERVER_TRANSPORT == "stdio":
                await self._run_stdio()
            elif settings.SERVER_TRANSPORT == "http":
                await self._run_http()
            else:
                raise ValueError(f"Unknown transport: {settings.SERVER_TRANSPORT}")

        finally:
            if self.tracing:
                self.tracing.shutdown()

    async def _run_stdio(self) -> None:
        self.logger.info("Starting MCP server with STDIO transport")
        await self.mcp.run_stdio_async()

    async def _run_http(self) -> None:
        self.logger.info(
            "Starting MCP server with HTTP transport on %s:%d",
            settings.HTTP_BIND_HOST, settings.HTTP_BIND_PORT,
        )
        await self.mcp.run_http_async(host=settings.HTTP_BIND_HOST, port=settings.HTTP_BIND_PORT)


def create_server() -> TrakSYSMCPServer:
    return TrakSYSMCPServer()


async def main() -> None:
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