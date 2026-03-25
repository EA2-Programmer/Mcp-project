import logging
import time
import uuid
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from .models import ChatCompletionRequest, ChatCompletionResponse, ChatCompletionResponseChoice, ChatMessage, \
    ModelListResponse, ModelObject
from agent.orchestrator import AgentOrchestrator
from config.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# This will be injected by main.py
orchestrator: AgentOrchestrator = None


def get_orchestrator():
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Agent Orchestrator not initialized")
    return orchestrator


@router.get("/models", response_model=ModelListResponse)
async def list_models():
    """Endpoint for model discovery (required by OpenWebUI)."""
    return ModelListResponse(
        data=[
            ModelObject(id=settings.agent_model_name)
        ]
    )


@router.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest, orch: AgentOrchestrator = Depends(get_orchestrator)):
    """OpenAI-compatible chat completions endpoint with SSE streaming."""

    logger.info(f"Received chat request for model: {request.model} | Stream: {request.stream}")

    # Convert incoming messages to dict format for the orchestrator
    messages = [m.model_dump(exclude_none=True) for m in request.messages]

    request_id = f"chatcmpl-{uuid.uuid4()}"
    created_time = int(time.time())

    # --- 1. STREAMING RESPONSE (OpenWebUI Default) ---
    if request.stream:
        async def generate_stream():
            try:
                async for chunk in orch.chat(messages):
                    # Format as OpenAI SSE chunk
                    response_chunk = {
                        "id": request_id,
                        "object": "chat.completion.chunk",
                        "created": created_time,
                        "model": request.model,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": chunk},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(response_chunk)}\n\n"

                # Send the final 'stop' reason
                final_chunk = {
                    "id": request_id,
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": request.model,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"

            except Exception as e:
                logger.error(f"Streaming error in chat_completions: {e}", exc_info=True)
                # Gracefully send the error to the UI instead of crashing silently
                error_chunk = {
                    "id": request_id,
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": request.model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": f"\n\n**System Error:** {str(e)}"},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(error_chunk)}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(generate_stream(), media_type="text/event-stream")

    # --- 2. STANDARD RESPONSE (Fallback) ---
    else:
        try:
            full_response = ""
            async for chunk in orch.chat(messages):
                full_response += chunk

            return ChatCompletionResponse(
                id=request_id,
                model=request.model,
                created=created_time,
                choices=[
                    ChatCompletionResponseChoice(
                        index=0,
                        message=ChatMessage(role="assistant", content=full_response),
                        finish_reason="stop"
                    )
                ]
            )
        except Exception as e:
            logger.error(f"Error in chat_completions: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))