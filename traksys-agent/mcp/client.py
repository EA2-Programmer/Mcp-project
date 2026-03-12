import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from .subprocess_manager import MCPSubprocessManager
from .protocol import JSONRPCHelper

class MCPClient:
    """Async client to communicate with TrakSYS MCP server via STDIO."""
    
    def __init__(self, manager: MCPSubprocessManager):
        self.manager = manager
        self.logger = logging.getLogger(__name__)
        self.request_id = 0
        self._response_futures: Dict[int, asyncio.Future] = {}
        self._read_task: Optional[asyncio.Task] = None

    async def connect(self):
        """Start the server and begin reading stdout and stderr."""
        await self.manager.start()
        self._read_task = asyncio.create_task(self._read_loop())
        self._stderr_task = asyncio.create_task(self._stderr_loop())
        
        # Initialize the MCP connection (handshake)
        await self.initialize()

    async def _stderr_loop(self):
        """Continuous loop to read stderr from the MCP server and log it."""
        try:
            while True:
                line = await self.manager.process.stderr.readline()
                if not line:
                    break
                # Log server's stderr to the agent's log
                self.logger.info(f"MCP-SERVER: {line.decode().strip()}")
        except Exception as e:
            self.logger.error(f"Stderr loop error: {e}")

    async def initialize(self):
        """Perform MCP initialization handshake."""
        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "traksys-agent", "version": "1.0.0"}
        }
        return await self.call("initialize", params)

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Retrieve the list of available tools from the server."""
        response = await self.call("tools/list")
        return response.get("result", {}).get("tools", [])

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific tool."""
        params = {
            "name": name,
            "arguments": arguments
        }
        response = await self.call("tools/call", params)
        return response.get("result", {})

    async def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a JSON-RPC request and wait for the response."""
        self.request_id += 1
        current_id = self.request_id
        
        future = asyncio.get_running_loop().create_future()
        self._response_futures[current_id] = future
        
        request_json = JSONRPCHelper.create_request(method, params, current_id)
        self.manager.process.stdin.write(request_json.encode())
        await self.manager.process.stdin.drain()
        
        try:
            # Wait for response with a timeout
            return await asyncio.wait_for(future, timeout=60.0)
        except asyncio.TimeoutError:
            self.logger.error(f"Request {current_id} ({method}) timed out.")
            del self._response_futures[current_id]
            raise
        except Exception as e:
            self.logger.error(f"Error during call {method}: {e}")
            raise

    async def _read_loop(self):
        """Continuous loop to read stdout from the MCP server."""
        try:
            while True:
                line = await self.manager.process.stdout.readline()
                if not line:
                    break
                
                response = JSONRPCHelper.parse_response(line.decode())
                resp_id = response.get("id")
                
                if resp_id in self._response_futures:
                    self._response_futures[resp_id].set_result(response)
                    del self._response_futures[resp_id]
                else:
                    # Log notifications or stray messages
                    self.logger.debug(f"Received notification: {response}")
        except Exception as e:
            self.logger.error(f"Read loop error: {e}")

    async def disconnect(self):
        """Cleanup and stop the server."""
        if self._read_task:
            self._read_task.cancel()
        await self.manager.stop()
