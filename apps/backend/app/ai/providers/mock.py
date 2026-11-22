import asyncio
import json

from app.ai.base import AIProvider, ChatContext, ImageInput
from app.core.errors import AIProviderError

DEFAULT_REPLY = {
    "speech": "Hola, estoy funcionando.",
    "emotion": "happy",
    "emotion_intensity": 0.8,
    "gesture": "nod",
    "look_at_user": True,
}

# Lets you preview every expression without a real model: "ponte triste" -> sad.
KEYWORD_REPLIES: dict[str, dict[str, object]] = {
    "triste": {"speech": "Oh... eso me pone un poco triste.", "emotion": "sad", "gesture": "sigh"},
    "sorpresa": {"speech": "¡¿En serio?!", "emotion": "surprised", "gesture": "none"},
    "enoja": {"speech": "Hmph. No me hace gracia.", "emotion": "annoyed", "gesture": "shake_head"},
    "piensa": {"speech": "Mmm, déjame pensarlo...", "emotion": "thinking", "gesture": "look_left"},
    "sueño": {"speech": "Tengo un poquito de sueño...", "emotion": "sleepy", "gesture": "stretch"},
    "vergüenza": {"speech": "N-no digas eso...", "emotion": "embarrassed", "gesture": "look_right"},
    "chiste": {"speech": "¡Jajaja, qué bueno!", "emotion": "excited", "gesture": "laugh"},
    "pregunta": {"speech": "¿Y eso cómo funciona?", "emotion": "curious", "gesture": "none"},
    "hola": {"speech": "¡Hola! Qué gusto verte.", "emotion": "happy", "gesture": "wave"},
}

ERROR_TRIGGER = "/error"


class MockAIProvider(AIProvider):
    """Offline provider for development. Costs nothing and needs no network."""

    name = "mock"
    is_remote = False

    def __init__(self, latency_seconds: float = 0.6) -> None:
        self._latency_seconds = latency_seconds

    async def chat(self, context: ChatContext) -> str:
        await asyncio.sleep(self._latency_seconds)
        last_user_content = next(
            (m.content for m in reversed(context.messages) if m.role == "user"), ""
        )
        # Ignore the app's bracketed per-turn instructions: react to what the user typed.
        last_user_text = last_user_content.split("\n\n[", 1)[0].lower()
        if last_user_text.strip() == ERROR_TRIGGER:
            raise AIProviderError("Simulated AI failure (mock provider)")
        return json.dumps(self._reply_for(last_user_text), ensure_ascii=False)

    async def analyze_image(self, image: ImageInput, prompt: str) -> str:
        await asyncio.sleep(self._latency_seconds)
        return f"Mock image description ({len(image.data)} bytes, {image.mime_type})."

    @staticmethod
    def _reply_for(text: str) -> dict[str, object]:
        for keyword, overrides in KEYWORD_REPLIES.items():
            if keyword in text:
                return {**DEFAULT_REPLY, "emotion_intensity": 0.7, **overrides}
        return DEFAULT_REPLY
