from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from app.ai.providers.mock import MockAIProvider
from app.config.settings import Settings
from app.main import create_app


@pytest.fixture
def app_settings(characters_dir: Path, tmp_path: Path) -> Settings:
    # Test characters: the real characters/ folder is personal and not in git.
    return Settings(
        _env_file=None,
        characters_dir=characters_dir,
        default_character="testy",
        memory_db=tmp_path / "memory.sqlite3",
        tts_url="http://127.0.0.1:9",  # never a real TTS service in tests
    )


@pytest.fixture
def client(app_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(app_settings, provider=MockAIProvider(latency_seconds=0))) as client:
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
    assert ready["character_id"] == "testy"
    assert {"id": "other", "name": "Other"} in ready["characters"]


def test_select_character_switches_and_broadcasts(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        receive(ws)  # session_ready
        ws.send_json({"type": "select_character", "character_id": "other"})
        changed = receive(ws)
        assert changed == {
            "type": "character_changed",
            "character_id": "other",
            "character_name": "Other",
            "history": [],
        }
    with client.websocket_connect("/ws") as ws:
        assert receive(ws)["character_id"] == "other"  # new connections see the switch


def test_unknown_character_is_reported(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        receive(ws)
        ws.send_json({"type": "select_character", "character_id": "nobody"})
        error = receive(ws)
    assert error["type"] == "error"
    assert error["code"] == "unknown_character"


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


def test_conversations_and_active_character_survive_a_restart(app_settings: Settings) -> None:
    provider = MockAIProvider(latency_seconds=0)
    with (
        TestClient(create_app(app_settings, provider=provider)) as client,
        client.websocket_connect("/ws") as ws,
    ):
        assert receive(ws)["history"] == []
        ws.send_json({"type": "user_message", "text": "me llamo James"})
        while receive(ws) != {"type": "state_changed", "state": "speaking"}:
            pass
        ws.send_json({"type": "select_character", "character_id": "other"})
        assert receive(ws)["type"] == "state_changed"  # speaking -> idle
        assert receive(ws)["history"] == []

    with (
        TestClient(create_app(app_settings, provider=provider)) as client,
        client.websocket_connect("/ws") as ws,
    ):
        ready = receive(ws)
        assert ready["character_id"] == "other"  # resumes the last active character
        assert ready["history"] == []
        ws.send_json({"type": "select_character", "character_id": "testy"})
        history = receive(ws)["history"]
    assert [e["role"] for e in history] == ["user", "assistant"]
    assert history[0]["text"] == "me llamo James"
    assert history[1]["emotion"] is not None


def test_clear_conversation_is_broadcast_and_persisted(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        receive(ws)
        ws.send_json({"type": "user_message", "text": "hola"})
        while receive(ws) != {"type": "state_changed", "state": "speaking"}:
            pass
        ws.send_json({"type": "clear_conversation"})
        assert receive(ws) == {"type": "state_changed", "state": "idle"}
        assert receive(ws) == {"type": "conversation_cleared", "character_id": "testy"}
    with client.websocket_connect("/ws") as ws:
        assert receive(ws)["history"] == []
