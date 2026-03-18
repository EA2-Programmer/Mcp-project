from openai import AsyncOpenAI
import logging
from config.settings import settings


class OpenAIClient:
    """Wrapper for OpenAI API interactions."""

    def __init__(self):
        # Initializes using the API key from your .env / settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.logger = logging.getLogger(__name__)

    async def get_completion(self, messages: list, tools: list = None, stream: bool = False):
        """Get a response from the configured OpenAI model."""
        try:
            # Start with the base arguments
            kwargs = {
                "model": settings.openai_model,
                "messages": messages,
                "stream": stream
            }

            # CRITICAL FIX for gpt-5 / reasoning models:
            # Only pass temperature if it is NOT 1.0.
            if settings.temperature != 1.0:
                kwargs["temperature"] = settings.temperature

            if tools:
                kwargs["tools"] = tools

                # If we are in the final streaming phase, force 'none'
                if stream:
                    kwargs["tool_choice"] = "none"
                else:
                    kwargs["tool_choice"] = "auto"

            self.logger.debug(f"Sending request to OpenAI (stream={stream}, tool_choice={kwargs.get('tool_choice')})")
            return await self.client.chat.completions.create(**kwargs)

        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            raise