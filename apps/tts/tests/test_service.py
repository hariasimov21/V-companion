from collections.abc import AsyncIterator
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from tts_service import server
from tts_service.server import _to_pcm16, create_app
from tts_service.voices import VoiceNotFoundError, find_voice, language_name


def make_voice(root: Path, character_id: str = "mimi") -> None:
    folder = root / character_id
    folder.mkdir(parents=True)
    (folder / "voice.wav").write_bytes(b"RIFF")
    (folder / "voice.txt").write_text("  Hola, genio.\n", encoding="utf-8")


def test_find_voice_reads_clip_and_transcript(tmp_path: Path) -> None:
    make_voice(tmp_path)
    voice = find_voice("mimi", tmp_path)
    assert voice.ref_audio == tmp_path / "mimi" / "voice.wav"
    assert voice.ref_text == "Hola, genio."


@pytest.mark.parametrize("character_id", ["../etc", "Mimi", "", "a/b"])
def test_find_voice_rejects_unsafe_ids(tmp_path: Path, character_id: str) -> None:
    with pytest.raises(VoiceNotFoundError):
        find_voice(character_id, tmp_path)


def test_find_voice_explains_missing_voice(tmp_path: Path) -> None:
    (tmp_path / "akari").mkdir()
    with pytest.raises(VoiceNotFoundError, match="make voice CHARACTER=akari"):
        find_voice("akari", tmp_path)


def test_language_names() -> None:
    assert language_name("es") == "Spanish"
    assert language_name("xx") == "Auto"


def test_pcm16_conversion_clips_and_scales() -> None:
    pcm = _to_pcm16(np.array([0.0, 1.0, -1.0, 2.0], dtype=np.float32))
    assert np.frombuffer(pcm, dtype="<i2").tolist() == [0, 32767, -32767, 32767]


class FakeEngine:
    def __init__(self, ready: bool) -> None:
        self.ready = ready
        self.error: str | None = None
        self.started = False

    def start(self) -> None:
        self.started = True

    def stream(self, voice: object, text: str, language: str) -> AsyncIterator[bytes]:
        async def chunks() -> AsyncIterator[bytes]:
            yield b"\x00\x01"
            yield b"\x02\x03"

        return chunks()


def test_speak_streams_pcm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_voice(tmp_path)
    monkeypatch.setattr(server, "find_voice", lambda cid: find_voice(cid, tmp_path))
    engine = FakeEngine(ready=True)
    with TestClient(create_app(engine)) as client:  # type: ignore[arg-type]
        assert engine.started
        assert client.get("/health").json()["ready"] is True
        response = client.post("/speak", json={"character_id": "mimi", "text": "hola"})
    assert response.status_code == 200
    assert response.headers["X-Sample-Rate"] == "24000"
    assert response.content == b"\x00\x01\x02\x03"


def test_speak_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "find_voice", lambda cid: find_voice(cid, tmp_path))

    def status(client: TestClient, character_id: str, text: str = "hola") -> int:
        payload = {"character_id": character_id, "text": text}
        return client.post("/speak", json=payload).status_code

    with TestClient(create_app(FakeEngine(ready=False))) as client:  # type: ignore[arg-type]
        assert status(client, "mimi") == 503  # still loading
    with TestClient(create_app(FakeEngine(ready=True))) as client:  # type: ignore[arg-type]
        assert status(client, "mimi") == 404  # no voice clip
        assert status(client, "../x") == 422
        assert status(client, "mimi", text="") == 422
