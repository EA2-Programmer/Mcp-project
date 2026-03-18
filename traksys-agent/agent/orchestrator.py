import json
import logging
import asyncio
from typing import AsyncGenerator, List, Dict, Any
from .openai_client import OpenAIClient
from .function_registry import FunctionRegistry
from mcp.client import MCPClient


class AgentOrchestrator:
    """The 'Brain' of the agent. Manages the LLM loop, parallel tool executions, and streaming."""

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
        """Main chat loop with multi-turn tool calling and SSE streaming support."""

        full_messages = [{"role": "system", "content": self.system_prompt}] + messages
        tools = await self.registry.get_openai_tools()
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            self.logger.info("Calling LLM to determine next action...")

            # Step 1: Use stream=False for the decision phase. It's much safer for parsing parallel tool calls.
            response = await self.openai_client.get_completion(
                messages=full_messages,
                tools=tools,
                stream=False
            )

            message = response.choices[0].message
            full_messages.append(message.model_dump(exclude_none=True))

            # Step 2: If the LLM wants to talk to the user directly, we break and STREAM the final response
            if not message.tool_calls:
                self.logger.info("No tool calls. Streaming final answer to user.")
                # Pop the last static message so we can re-request it as a stream
                full_messages.pop()

                stream_response = await self.openai_client.get_completion(
                    messages=full_messages,
                    tools=tools,
                    stream=True
                )

                async for chunk in stream_response:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
                break

            # Step 3: If tools are requested, execute them in PARALLEL
            self.logger.info(f"Executing {len(message.tool_calls)} tool(s) in parallel...")

            async def execute_single_tool(tool_call):
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                self.logger.info(f"Tool Request -> {tool_name}({tool_args})")

                try:
                    # MCP server call
                    result = await self.mcp_client.call_tool(tool_name, tool_args)
                    return {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": json.dumps(result)
                    }
                except Exception as e:
                    self.logger.error(f"Tool {tool_name} failed: {e}")
                    return {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": json.dumps(
                            {"status": "error", "error": str(e), "suggestions": ["Check parameters and try again."]})
                    }

            # Run all requested tools simultaneously using asyncio.gather
            tool_results = await asyncio.gather(*(execute_single_tool(tc) for tc in message.tool_calls))

            # Append all results to the conversation history
            full_messages.extend(tool_results)

            # The loop will now restart, feeding the tool results back to the LLM
        else:
            # Exceeded max_iterations — yield a safe fallback message
            self.logger.error("Agent exceeded max_iterations (%d). Returning fallback response.", max_iterations)
            yield "I wasn't able to complete this request — the reasoning loop exceeded its limit. Please try rephrasing your question or narrowing the scope."