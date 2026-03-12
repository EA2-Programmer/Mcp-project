from openai import AsyncOpenAI
import logging
from config.settings import settings

class OpenAIClient:
    """Wrapper for OpenAI API interactions."""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.logger = logging.getLogger(__name__)

    async def get_completion(self, messages: list, tools: list = None, stream: bool = False):
        """Get a response from GPT-4o, optionally with tool calling."""
        try:
            kwargs = {
                "model": settings.openai_model,
                "messages": messages,
                "temperature": settings.temperature,
                "stream": stream
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            
            return await self.client.chat.completions.create(**kwargs)
        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            raise
