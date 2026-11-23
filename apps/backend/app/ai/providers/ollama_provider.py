"""Local models served by Ollama (https://ollama.com) via its native /api/chat endpoint."""

import base64
from typing import Any

import httpx

from app.ai.base import AIProvider, ChatContext, ImageInput
from app.core.errors import AIProviderError, AITimeoutError
from app.core.logging import get_logger

log = get_logger("ai")

THINK_LEVELS = {"low", "medium", "high"}
# Only gpt-oss understands think levels. Other thinking models (qwen3, deepseek-r1...)
# take any level as "think at full length": 50 s for a greeting in a test with qwen3.
THINK_LEVEL_FAMILIES = {"gptoss"}
# Sampling tweaks per model family, on top of the shared options. qwen3 copies phrases from
# its own past replies into a catchphrase loop; presence_penalty (Qwen's recommendation)
# cut that from 8/12 to 3/12 replies when replaying a real looping conversation.
FAMILY_OPTIONS: dict[str, dict[str, Any]] = {"qwen3": {"presence_penalty": 1.0}}
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
        num_ctx: int | None = None,
        temperature: float = 0.8,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        self._model = model
        self._think = think
        # Capabilities reported by /api/show, per model ("completion", "thinking", ...).
        # None = this Ollama version does not report them.
        self._capabilities: dict[str, list[str] | None] = {}
        self._families: dict[str, str] = {}
        self._keep_alive = keep_alive
        # Same options on every request: a different num_ctx makes Ollama reload the model.
        self._options: dict[str, Any] = {"temperature": temperature}
        if num_ctx is not None:
            self._options["num_ctx"] = num_ctx
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_seconds, connect=5.0),
            transport=transport,
        )

    @property
    def context_window(self) -> int | None:
        num_ctx = self._options.get("num_ctx")
        return num_ctx if isinstance(num_ctx, int) else None

    @property
    def model(self) -> str:
        return self._model

    async def list_models(self) -> list[str]:
        """Installed models that can chat (embedding-only models are left out)."""
        data = await self._call("GET", "/api/tags")
        names = [
            m["name"]
            for m in data.get("models", [])
            if isinstance(m, dict) and isinstance(m.get("name"), str)
        ]
        chat_models = []
        for name in names:
            capabilities = await self._capabilities_of(name)
            if capabilities is None or "completion" in capabilities:
                chat_models.append(name)
        return sorted(chat_models)

    async def set_model(self, model: str) -> None:
        await self._capabilities_of(model)  # also fails early if it is not installed
        self._model = model
        log.info("Model selected", extra={"fields": {"model": model}})

    async def unload(self, model: str) -> None:
        """keep_alive=0 makes Ollama free the model's VRAM right away."""
        try:
            await self._call("POST", "/api/generate", {"model": model, "keep_alive": 0})
        except AIProviderError as exc:
            log.warning("Could not unload model", extra={"fields": {"error": exc.message}})

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
                {
                    "model": self._model,
                    "messages": [],
                    "keep_alive": self._keep_alive,
                    "options": self._options,
                },
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
            "options": await self._options_for_current_model(),
        }
        if response_format is not None:
            payload["format"] = response_format
        think = await self._think_for_current_model()
        if think is not None:
            payload["think"] = think

        for attempt in range(1 + EMPTY_REPLY_RETRIES):
            content = _extract_content(await self._request(payload))
            if content.strip():
                return content
            log.warning("Empty reply from model", extra={"fields": {"attempt": attempt + 1}})
        raise AIProviderError("The model returned an empty reply")

    async def _capabilities_of(self, model: str) -> list[str] | None:
        if model not in self._capabilities:
            data = await self._call("POST", "/api/show", {"model": model})
            details = data.get("details")
            family = details.get("family") if isinstance(details, dict) else None
            self._families[model] = family if isinstance(family, str) else ""
            capabilities = data.get("capabilities")
            self._capabilities[model] = (
                [c for c in capabilities if isinstance(c, str)]
                if isinstance(capabilities, list)
                else None
            )
        return self._capabilities[model]

    async def _options_for_current_model(self) -> dict[str, Any]:
        try:
            await self._capabilities_of(self._model)  # also learns the model family
        except AIProviderError:
            return self._options  # Let the chat request itself report the problem.
        return {**self._options, **FAMILY_OPTIONS.get(self._families.get(self._model, ""), {})}

    async def _think_for_current_model(self) -> bool | str | None:
        """OLLAMA_THINK only applies to models that can think; others reject the field."""
        if self._think is None:
            return None
        try:
            capabilities = await self._capabilities_of(self._model)
        except AIProviderError:
            return self._think  # Let the chat request itself report the problem.
        if capabilities is None:
            return self._think
        if "thinking" not in capabilities:
            return None
        if isinstance(self._think, str) and self._families.get(self._model) not in (
            THINK_LEVEL_FAMILIES
        ):
            # A companion chat cannot wait for full reasoning: low/medium/high mean "off".
            return False
        return self._think

    async def _request(
        self, payload: dict[str, Any], request_timeout: httpx.Timeout | None = None
    ) -> dict[str, Any]:
        return await self._call("POST", "/api/chat", payload, request_timeout)

    async def _call(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        request_timeout: httpx.Timeout | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._client.request(
                method, path, json=payload, timeout=request_timeout or self._client.timeout
            )
        except httpx.TimeoutException as exc:
            raise AITimeoutError("Ollama took too long to answer") from exc
        except httpx.TransportError as exc:
            raise AIProviderError(
                f"Cannot reach Ollama at {self._base_url}. Is it running?"
            ) from exc

        if response.status_code == 404:
            model = (payload or {}).get("model", self._model)
            raise AIProviderError(f"Ollama model '{model}' not found. Run: ollama pull {model}")
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
