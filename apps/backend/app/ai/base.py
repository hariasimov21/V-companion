from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel

Role = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    role: Role
    content: str


class ChatContext(BaseModel):
    system_prompt: str
    messages: list[ChatMessage]
    # JSON schema the reply must follow; providers with structured output enforce it.
    response_schema: dict[str, Any] | None = None


class ImageInput(BaseModel):
    data: bytes
    mime_type: str = "image/jpeg"


class AIProvider(ABC):
    """Provider-agnostic AI interface.

    `chat` returns the raw model output; turning it into an `AssistantReply` is the
    job of `app.ai.response_parser`, so every provider gets the same validation.
    Providers must raise `AIProviderError` (or subclasses) on failure.
    """

    name: str
    is_remote: bool

    @abstractmethod
    async def chat(self, context: ChatContext) -> str: ...

    @abstractmethod
    async def analyze_image(self, image: ImageInput, prompt: str) -> str: ...

    @property
    def model(self) -> str | None:
        """The model in use, when the provider exposes it."""
        return None

    async def list_models(self) -> list[str]:
        """Chat models the user can switch to. Empty means switching is not supported."""
        return []

    async def set_model(self, model: str) -> None:
        """Switches to another model from `list_models()`."""
        raise NotImplementedError(f"{self.name} does not support switching models")

    async def unload(self, model: str) -> None:  # noqa: B027 - optional hook, no-op by default
        """Optional: free the memory (e.g. VRAM) held by a model that is no longer used."""

    async def warm_up(self) -> None:  # noqa: B027 - optional hook, no-op by default
        """Optional: prepare the model (e.g. load it into memory) before the first turn."""

    async def aclose(self) -> None:  # noqa: B027 - optional hook, no-op by default
        """Optional: release network clients or other resources on shutdown."""
