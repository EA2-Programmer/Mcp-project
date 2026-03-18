import logging
import asyncio
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from config.settings import settings
from mcp.subprocess_manager import MCPSubprocessManager
from mcp.client import MCPClient
from agent.openai_client import OpenAIClient
from agent.function_registry import FunctionRegistry
from agent.orchestrator import AgentOrchestrator
from api import routes

# Setup basic logging for the agent
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

# Resource lifecycle management
mcp_manager: MCPSubprocessManager = None
mcp_client: MCPClient = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown of MCP resources."""
    global mcp_manager, mcp_client
    
    logger.info("Starting TrakSYS Agent API...")
    
    # 1. Load System Prompt
    prompt_path = "traksys-agent/config/prompts/system_prompt.md"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
    except Exception as e:
        logger.error(f"Failed to load system prompt: {e}")
        system_prompt = "You are a manufacturing expert."

    # 2. Initialize MCP components
    mcp_manager = MCPSubprocessManager(
        server_path=settings.mcp_server_path,
        env_vars=settings.mcp_env_vars
    )
    mcp_client = MCPClient(mcp_manager)
    await mcp_client.connect()
    
    # 3. Initialize Agent components
    openai_client = OpenAIClient()
    registry = FunctionRegistry(mcp_client)
    orchestrator = AgentOrchestrator(
        openai_client=openai_client,
        mcp_client=mcp_client,
        function_registry=registry,
        system_prompt=system_prompt
    )
    
    # 4. Inject orchestrator into routes
    routes.orchestrator = orchestrator
    
    logger.info("✓ TrakSYS Agent API is ready")
    
    yield
    
    # Shutdown
    logger.info("Shutting down TrakSYS Agent API...")
    if mcp_client:
        await mcp_client.disconnect()

app = FastAPI(
    title="TrakSYS Manufacturing Expert API",
    version="1.0.0",
    lifespan=lifespan
)

# Robust CORS for OpenWebUI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logger middleware to debug Docker connectivity
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    formatted_process_time = "{0:.2f}".format(process_time)
    logger.info(f"Incoming Request: {request.method} {request.url.path} | Status: {response.status_code} | {formatted_process_time}ms")
    return response

@app.get("/")
async def root():
    return RedirectResponse(url="/v1/models")

@app.get("/health")
async def health():
    return {"status": "ok", "mcp_connected": mcp_manager.process is not None if mcp_manager else False}

app.include_router(routes.router, prefix="/v1")

if __name__ == "__main__":
    import uvicorn
    # Listen on all interfaces so Docker can connect
    uvicorn.run(app, host="0.0.0.0", port=8000)
