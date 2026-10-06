import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.ai.base import ChatContext, ChatMessage, ImageInput
from app.ai.factory import create_ai_provider
from app.ai.providers.ollama_provider import OllamaProvider, parse_think_setting
from app.config.settings import AIProviderName, Settings
from app.core.errors import AIProviderError, AITimeoutError, ConfigError

Handler = Callable[[httpx.Request], httpx.Response]

CONTEXT = ChatContext(
    system_prompt="Eres Akari.",
    messages=[
        ChatMessage(role="user", content="hola"),
        ChatMessage(role="assistant", content="¡Hola!"),
        ChatMessage(role="user", content="¿qué tal?"),
    ],
    response_schema={"type": "object", "properties": {"speech": {"type": "string"}}},
)


def ok_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})


def make_provider(handler: Handler, **kwargs: Any) -> OllamaProvider:
    return OllamaProvider(
        base_url="http://ollama.test",
        model="gpt-oss:latest",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


@pytest.mark.anyio
async def test_chat_sends_history_schema_and_options() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return ok_response('{"speech": "Bien"}')

    provider = make_provider(handler, think="low", keep_alive="10m")
    assert await provider.chat(CONTEXT) == '{"speech": "Bien"}'

    body = captured["body"]
    assert captured["path"] == "/api/chat"
    assert body["model"] == "gpt-oss:latest"
    assert body["stream"] is False
    assert body["think"] == "low"
    assert body["keep_alive"] == "10m"
    assert body["format"] == CONTEXT.response_schema
    assert [m["role"] for m in body["messages"]] == ["system", "user", "assistant", "user"]
    assert body["messages"][0]["content"] == "Eres Akari."


@pytest.mark.anyio
async def test_think_and_format_are_omitted_when_unset() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return ok_response("{}")

    await make_provider(handler).chat(CONTEXT.model_copy(update={"response_schema": None}))
    assert "think" not in captured
    assert "format" not in captured


@pytest.mark.anyio
async def test_analyze_image_sends_base64_image() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return ok_response("Una taza de café.")

    result = await make_provider(handler).analyze_image(ImageInput(data=b"abc"), "¿Qué ves?")
    assert result == "Una taza de café."
    assert captured["messages"][0]["images"] == ["YWJj"]


@pytest.mark.anyio
async def test_missing_model_gives_actionable_error() -> None:
    provider = make_provider(lambda _: httpx.Response(404, json={"error": "model not found"}))
    with pytest.raises(AIProviderError, match="ollama pull gpt-oss:latest"):
        await provider.chat(CONTEXT)


@pytest.mark.anyio
async def test_server_error_includes_detail() -> None:
    provider = make_provider(lambda _: httpx.Response(500, json={"error": "out of memory"}))
    with pytest.raises(AIProviderError, match="out of memory"):
        await provider.chat(CONTEXT)


@pytest.mark.anyio
async def test_unreachable_server() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(AIProviderError, match="Cannot reach Ollama"):
        await make_provider(handler).chat(CONTEXT)


@pytest.mark.anyio
async def test_timeout_maps_to_ai_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(AITimeoutError):
        await make_provider(handler).chat(CONTEXT)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [httpx.Response(200, text="not json"), httpx.Response(200, json={"done": True})],
)
async def test_malformed_response(response: httpx.Response) -> None:
    with pytest.raises(AIProviderError):
        await make_provider(lambda _: response).chat(CONTEXT)


@pytest.mark.anyio
async def test_empty_reply_is_retried_once() -> None:
    replies = iter(["", '{"speech": "Hola"}'])
    provider = make_provider(lambda _: ok_response(next(replies)))
    assert await provider.chat(CONTEXT) == '{"speech": "Hola"}'


@pytest.mark.anyio
async def test_repeated_empty_reply_raises() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return ok_response("  ")

    with pytest.raises(AIProviderError, match="empty reply"):
        await make_provider(handler).chat(CONTEXT)
    assert calls == 2


@pytest.mark.anyio
async def test_warm_up_failure_is_not_fatal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    await make_provider(handler).warm_up()  # must not raise


@pytest.mark.parametrize(
    ("value", "expected"),
    [("", None), ("low", "low"), (" HIGH ", "high"), ("true", True), ("false", False)],
)
def test_parse_think_setting(value: str, expected: bool | str | None) -> None:
    assert parse_think_setting(value) == expected


def test_parse_think_setting_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_think_setting("maximum")


def test_factory_builds_ollama_provider() -> None:
    settings = Settings(
        _env_file=None,
        ai_provider=AIProviderName.OLLAMA,
        ollama_model="gpt-oss:latest",
        ollama_think="low",
    )
    assert isinstance(create_ai_provider(settings), OllamaProvider)


@pytest.mark.parametrize(("model", "think"), [("", "low"), ("gpt-oss:latest", "maximum")])
def test_factory_rejects_invalid_ollama_config(model: str, think: str) -> None:
    settings = Settings(
        _env_file=None, ai_provider=AIProviderName.OLLAMA, ollama_model=model, ollama_think=think
    )
    with pytest.raises(ConfigError):
        create_ai_provider(settings)
