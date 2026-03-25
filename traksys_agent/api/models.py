from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union

class ChatMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: Optional[bool] = False
    temperature: Optional[float] = 0.7
    # max_tokens: Optional[int] = 2000

class ChatCompletionResponseChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = "stop"

class ChatCompletionResponse(BaseModel):
    id: str = "chatcmpl-default"
    object: str = "chat.completion"
    created: int = 123456789
    model: str
    choices: List[ChatCompletionResponseChoice]
    usage: Optional[Dict[str, int]] = None

class ModelObject(BaseModel):
    id: str
    object: str = "model"
    created: int = 123456789
    owned_by: str = "traksys"

class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelObject]
