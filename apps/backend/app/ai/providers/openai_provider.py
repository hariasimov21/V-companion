from pydantic import SecretStr

from app.ai.base import AIProvider, ChatContext, ImageInput
from app.core.errors import AIProviderError


class OpenAIProvider(AIProvider):
    """Placeholder. Real implementation (chat + vision + streaming) lands in a later phase.

    Realtime voice will live in a separate `openai_realtime.py` service so the
    request/response chat path stays simple.
    """

    name = "openai"
    is_remote = True

    def __init__(self, api_key: SecretStr, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def chat(self, context: ChatContext) -> str:
        raise AIProviderError("OpenAI provider is not implemented yet. Use AI_PROVIDER=mock.")

    async def analyze_image(self, image: ImageInput, prompt: str) -> str:
        raise AIProviderError("OpenAI vision is not implemented yet.")
