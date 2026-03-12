import logging
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException
from .models import ChatCompletionRequest, ChatCompletionResponse, ChatCompletionResponseChoice, ChatMessage, ModelListResponse, ModelObject
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

@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest, orch: AgentOrchestrator = Depends(get_orchestrator)):
    """OpenAI-compatible chat completions endpoint."""
    
    logger.info(f"Received chat request for model: {request.model}")
    
    # Convert incoming messages to dict format for the orchestrator
    messages = [m.model_dump(exclude_none=True) for m in request.messages]
    
    try:
        # Generate response using the orchestrator
        # Note: Current orchestrator is a generator, so we collect the final result
        full_response = ""
        async for chunk in orch.chat(messages):
            full_response += chunk
            
        # Format as OpenAI response
        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4()}",
            model=request.model,
            created=int(time.time()),
            choices=[
                ChatCompletionResponseChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=full_response)
                )
            ]
        )
        
    except Exception as e:
        logger.error(f"Error in chat_completions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
