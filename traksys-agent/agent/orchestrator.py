import json
import logging
from typing import AsyncGenerator, List, Dict, Any
from .openai_client import OpenAIClient
from .function_registry import FunctionRegistry
from mcp.client import MCPClient

class AgentOrchestrator:
    """The 'Brain' of the agent. Manages the LLM loop and tool executions."""
    
    def __init__(
        self, 
        openai_client: OpenAIClient, 
        mcp_client: MCPClient,
        function_registry: FunctionRegistry,
        system_prompt: str
    ):
        self.openai_client = openai_client
        self.mcp_client = mcp_client
        self.registry = function_registry
        self.system_prompt = system_prompt
        self.logger = logging.getLogger(__name__)

    async def chat(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Main chat loop with multi-turn tool calling support."""
        
        # 1. Prepare messages with system prompt
        full_messages = [{"role": "system", "content": self.system_prompt}] + messages
        
        # 2. Get available tools in OpenAI format
        tools = await self.registry.get_openai_tools()
        
        while True:
            # 3. Call OpenAI
            response = await self.openai_client.get_completion(
                messages=full_messages,
                tools=tools,
                stream=False # Start with non-streaming for tool-logic complexity
            )
            
            message = response.choices[0].message
            full_messages.append(message)
            
            # 4. Check if LLM wants to call a tool
            if not message.tool_calls:
                # No more tools needed, yield the final text
                yield message.content
                break
            
            # 5. Execute tool calls
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                self.logger.info(f"Executing tool: {tool_name} with args: {tool_args}")
                
                try:
                    # Call the actual MCP tool
                    result = await self.mcp_client.call_tool(tool_name, tool_args)
                    
                    # Add tool result to conversation
                    full_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": json.dumps(result)
                    })
                except Exception as e:
                    self.logger.error(f"Tool execution failed: {e}")
                    full_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": json.dumps({"error": str(e)})
                    })
            
            # 6. Loop continues: LLM will now receive tool results and generate final answer
