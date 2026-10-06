from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from app.ai.providers.mock import MockAIProvider
from app.config.settings import Settings
from app.main import create_app


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings, provider=MockAIProvider(latency_seconds=0))) as client:
        yield client


def receive(ws: WebSocketTestSession) -> dict[str, Any]:
    data: dict[str, Any] = ws.receive_json()
    return data


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_session_ready_is_sent_on_connect(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        ready = receive(ws)
    assert ready["type"] == "session_ready"
    assert ready["ai_provider"] == "mock"
    assert ready["ai_is_remote"] is False
    assert ready["privacy"]["camera_enabled"] is False
    assert ready["state"] == "idle"


def test_full_turn(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        receive(ws)  # session_ready
        ws.send_json({"type": "user_message", "text": "hola?"})

        assert receive(ws) == {"type": "state_changed", "state": "thinking"}
        message = receive(ws)
        assert message["type"] == "assistant_message"
        assert message["emotion"] in {"happy"}
        assert receive(ws) == {"type": "state_changed", "state": "speaking"}

        ws.send_json({"type": "speech_finished"})
        assert receive(ws) == {"type": "state_changed", "state": "idle"}


def test_invalid_message_returns_error_and_keeps_connection(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        receive(ws)
        ws.send_text("not json")
        assert receive(ws)["code"] == "invalid_message"
        ws.send_json({"type": "execute_command", "command": "ls"})
        assert receive(ws)["code"] == "invalid_message"


def test_ai_error_is_reported_to_client(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        receive(ws)
        ws.send_json({"type": "user_message", "text": "/error"})
        assert receive(ws)["state"] == "thinking"
        assert receive(ws)["state"] == "error"
        error = receive(ws)
        assert error["type"] == "error"
        assert error["code"] == "ai_provider_error"
