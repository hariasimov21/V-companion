"""Local models served by Ollama (https://ollama.com) via its native /api/chat endpoint."""

import base64
from typing import Any

import httpx

from app.ai.base import AIProvider, ChatContext, ImageInput
from app.core.errors import AIProviderError, AITimeoutError
from app.core.logging import get_logger

log = get_logger("ai")

THINK_LEVELS = {"low", "medium", "high"}
# Loading a large model from disk can take much longer than a normal chat turn.
WARM_UP_TIMEOUT = httpx.Timeout(180.0, connect=5.0)
# Thinking models occasionally spend the whole turn reasoning and return no content.
EMPTY_REPLY_RETRIES = 1


def parse_think_setting(value: str) -> bool | str | None:
    """Maps OLLAMA_THINK to Ollama's `think` field; None means "use the model default"."""
    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized in THINK_LEVELS:
        return normalized
    if normalized in {"true", "false"}:
        return normalized == "true"
    raise ValueError(f"Invalid OLLAMA_THINK value: {value!r}")


class OllamaProvider(AIProvider):
    name = "ollama"
    is_remote = False

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float,
        think: bool | str | None = None,
        keep_alive: str = "30m",
        temperature: float = 0.8,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        self._model = model
        self._think = think
        self._keep_alive = keep_alive
        self._temperature = temperature
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_seconds, connect=5.0),
            transport=transport,
        )

    async def chat(self, context: ChatContext) -> str:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": context.system_prompt},
            *({"role": m.role, "content": m.content} for m in context.messages),
        ]
        return await self._post_chat(messages, response_format=context.response_schema)

    async def analyze_image(self, image: ImageInput, prompt: str) -> str:
        encoded = base64.b64encode(image.data).decode("ascii")
        messages = [{"role": "user", "content": prompt, "images": [encoded]}]
        return await self._post_chat(messages, response_format=None)

    async def warm_up(self) -> None:
        """An empty chat request makes Ollama load the model into memory."""
        try:
            await self._request(
                {"model": self._model, "messages": [], "keep_alive": self._keep_alive},
                request_timeout=WARM_UP_TIMEOUT,
            )
            log.info("Model loaded", extra={"fields": {"model": self._model}})
        except AIProviderError as exc:
            log.warning("Model warm-up failed", extra={"fields": {"error": exc.message}})

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _post_chat(
        self, messages: list[dict[str, Any]], response_format: dict[str, Any] | None
    ) -> str:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "keep_alive": self._keep_alive,
            "options": {"temperature": self._temperature},
        }
        if response_format is not None:
            payload["format"] = response_format
        if self._think is not None:
            payload["think"] = self._think

        for attempt in range(1 + EMPTY_REPLY_RETRIES):
            content = _extract_content(await self._request(payload))
            if content.strip():
                return content
            log.warning("Empty reply from model", extra={"fields": {"attempt": attempt + 1}})
        raise AIProviderError("The model returned an empty reply")

    async def _request(
        self, payload: dict[str, Any], request_timeout: httpx.Timeout | None = None
    ) -> dict[str, Any]:
        try:
            response = await self._client.post(
                "/api/chat", json=payload, timeout=request_timeout or self._client.timeout
            )
        except httpx.TimeoutException as exc:
            raise AITimeoutError("Ollama took too long to answer") from exc
        except httpx.TransportError as exc:
            raise AIProviderError(
                f"Cannot reach Ollama at {self._base_url}. Is it running?"
            ) from exc

        if response.status_code == 404:
            raise AIProviderError(
                f"Ollama model '{self._model}' not found. Run: ollama pull {self._model}"
            )
        if response.is_error:
            raise AIProviderError(f"Ollama error {response.status_code}: {_error_detail(response)}")
        try:
            data: dict[str, Any] = response.json()
        except ValueError as exc:
            raise AIProviderError("Ollama returned invalid JSON") from exc
        return data


def _extract_content(data: dict[str, Any]) -> str:
    message = data.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise AIProviderError("Ollama returned an unexpected response")
    return content


def _error_detail(response: httpx.Response) -> str:
    try:
        detail = response.json().get("error")
    except ValueError:
        detail = None
    return str(detail or response.reason_phrase)[:200]
