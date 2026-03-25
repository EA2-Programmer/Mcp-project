from typing import List, Dict, Any
from ..mcp.client import MCPClient


class FunctionRegistry:
    """Converts MCP tools into OpenAI-compatible function definitions."""

    def __init__(self, mcp_client: MCPClient):
        self.mcp_client = mcp_client
        self.cached_tools: List[Dict[str, Any]] = []

    async def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Fetch tools from MCP and convert to OpenAI 'tools' format."""
        if not self.cached_tools:
            await self.refresh()
        return self.cached_tools

    async def refresh(self) -> None:
        """Force a re-fetch of the tool list from MCP. Call this after updating MCP tools."""
        mcp_tools = await self.mcp_client.list_tools()
        self.cached_tools = [
            self._convert_to_openai(tool) for tool in mcp_tools
        ]

    def _convert_to_openai(self, mcp_tool: Dict[str, Any]) -> Dict[str, Any]:
        """Maps an MCP tool schema to OpenAI tool schema."""
        return {
            "type": "function",
            "function": {
                "name": mcp_tool["name"],
                "description": mcp_tool.get("description", ""),
                "parameters": mcp_tool.get("inputSchema", {
                    "type": "object",
                    "properties": {},
                    "required": []
                })
            }
        }