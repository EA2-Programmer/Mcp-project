import asyncio
import os
from typing import Optional
import logging

class MCPSubprocessManager:
    """Manages the lifecycle of the TrakSYS MCP server subprocess."""
    
    def __init__(self, server_path: str, env_vars: dict):
        self.server_path = server_path
        self.env_vars = env_vars
        self.process: Optional[asyncio.subprocess.Process] = None
        self.logger = logging.getLogger(__name__)

    async def start(self):
        """Start the MCP server as a module subprocess."""
        if self.process:
            self.logger.warning("MCP server process already running.")
            return

        self.logger.info("Starting MCP server as module: src.traksys_mcp.server")
        
        env = os.environ.copy()
        env.update(self.env_vars)
        
        # Set PYTHONPATH to the current directory so it can find the 'src' package
        env["PYTHONPATH"] = os.getcwd()
        
        try:
            self.process = await asyncio.create_subprocess_exec(
                "python", "-m", "src.traksys_mcp.server",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            self.logger.info(f"✓ MCP server started (PID: {self.process.pid})")
        except Exception as e:
            self.logger.error(f"Failed to start MCP server: {e}")
            raise

    async def stop(self):
        """Stop the MCP server subprocess."""
        if self.process:
            self.logger.info("Stopping MCP server...")
            self.process.terminate()
            await self.process.wait()
            self.process = None
            self.logger.info("✓ MCP server stopped")
