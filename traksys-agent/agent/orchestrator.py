import json
import logging
import time
from typing import AsyncGenerator, List, Dict, Any

from .openai_client import OpenAIClient
from .function_registry import FunctionRegistry
from mcp.client import MCPClient

# Simplified import - no more register_instance / init_tracing
from src.traksys_mcp.services.langfuse_tracing import TracingService, _NoOpSpan


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

        # Direct instantiation - clean and reliable
        self.tracing = TracingService()

    async def chat(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Main chat loop with multi-turn tool calling support."""

        user_query = messages[-1].get("content", "") if messages else ""

        async with self.tracing.trace_chat(
                user_query=user_query,
                messages=messages,
                model="gpt-4o",
                agent_name="TrakSYS-Agent"
        ) as trace:

            is_tracing_enabled = not isinstance(trace, _NoOpSpan)
            full_messages = [{"role": "system", "content": self.system_prompt}] + messages
            tools = await self.registry.get_openai_tools()

            final_answer = ""
            turn = 0

            try:
                while True:
                    turn += 1

                    if is_tracing_enabled:
                        llm_span = self.tracing.record_llm_call(
                            parent=trace,
                            turn=turn,
                            messages_count=len(full_messages),
                            tools_count=len(tools)
                        )
                    else:
                        llm_span = _NoOpSpan()

                    response = await self.openai_client.get_completion(
                        messages=full_messages,
                        tools=tools,
                        stream=False,
                    )

                    message = response.choices[0].message
                    full_messages.append(message)

                    if is_tracing_enabled:
                        llm_span.update(output={
                            "has_tool_calls": bool(message.tool_calls),
                            "tool_call_count": len(message.tool_calls) if message.tool_calls else 0,
                            "content_preview": (message.content or "")[:200],
                        })
                        llm_span.end()

                    if not message.tool_calls:
                        final_answer = message.content
                        yield message.content
                        break

                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)

                        self.logger.info(f"Executing tool: {tool_name}")

                        if is_tracing_enabled:
                            tool_span = trace.span(
                                name=f"tools/call_{tool_name}",
                                input={
                                    "tool_name": tool_name,
                                    "raw_arguments": tool_args,
                                },
                                metadata={"tool_call_id": tool_call.id},
                            )
                        else:
                            tool_span = _NoOpSpan()

                        t_start = time.monotonic()
                        try:
                            result = await self.mcp_client.call_tool(tool_name, tool_args)
                            latency_ms = round((time.monotonic() - t_start) * 1000)

                            if is_tracing_enabled:
                                tool_span.update(
                                    output={
                                        "raw_result": result,
                                        "status": "success",
                                        "latency_ms": latency_ms,
                                    },
                                    metadata={"latency_ms": latency_ms},
                                )
                                tool_span.end()

                            full_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_name,
                                "content": json.dumps(result),
                            })

                        except Exception as e:
                            self.logger.error(f"Tool failed: {e}")
                            if is_tracing_enabled:
                                tool_span.update(
                                    output={"error": str(e)},
                                    level="ERROR",
                                    status_message=str(e),
                                )
                                tool_span.end()

                            full_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_name,
                                "content": json.dumps({"error": str(e)}),
                            })

            except Exception as e:
                self.logger.error(f"Agent chat failed: {e}")
                if is_tracing_enabled:
                    self.tracing.record_error(trace, e, "agent_chat")
                raise

            finally:
                if is_tracing_enabled:
                    self.tracing.set_trace_output(trace, {
                        "final_answer": final_answer[:500],
                        "total_turns": turn,
                    })
                    self.tracing.shutdown()