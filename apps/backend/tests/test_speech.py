import asyncio
import base64
import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel

from app.ai.base import AIProvider, ChatContext
from app.ai.providers.mock import MockAIProvider
from app.character.config import load_character_config
from app.character.registry import Character
from app.character.service import CharacterService
from app.character.state import CharacterStateStore
from app.conversation.service import ConversationService
from app.memory.store import InMemoryConversationStore
from app.models.protocol import AssistantMessage, SpeechAudio, SpeechEnd, VoiceChanged
from app.speech.service import SpeechService
from app.speech.text import speakable_text
from app.speech.tts_client import TTSClient, TTSUnavailableError


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[BaseModel] = []

    async def publish(self, event: BaseModel) -> None:
        self.events.append(event)

    def of(self, kind: type[BaseModel]) -> list[BaseModel]:
        return [e for e in self.events if isinstance(e, kind)]


class FakeTTS:
    """Stands in for TTSClient: yields the given byte chunks, optionally slowly or failing."""

    def __init__(self, chunks: list[bytes], delay: float = 0.0, fail: bool = False) -> None:
        self.chunks, self.delay, self.fail = chunks, delay, fail
        self.requests: list[tuple[str, str, str]] = []
        self.ready = True

    async def is_ready(self) -> bool:
        return self.ready

    async def stream(
        self, character_id: str, text: str, language: str
    ) -> AsyncIterator[tuple[int, bytes]]:
        self.requests.append((character_id, text, language))
        for chunk in self.chunks:
            await asyncio.sleep(self.delay)
            yield 24000, chunk
        if self.fail:
            raise TTSUnavailableError("boom")

    async def aclose(self) -> None:
        pass


def make_character(tmp_path: Path, character_file: Path, with_voice: bool = True) -> Character:
    folder = tmp_path / "characters" / "testy"
    folder.mkdir(parents=True, exist_ok=True)
    if with_voice:
        (folder / "voice.wav").write_bytes(b"RIFF")
        (folder / "voice.txt").write_text("Hola.", encoding="utf-8")
    return Character("testy", CharacterService(load_character_config(character_file)))


def make_speech(
    tmp_path: Path, tts: FakeTTS, store: InMemoryConversationStore | None = None
) -> tuple[SpeechService, RecordingPublisher]:
    publisher = RecordingPublisher()
    speech = SpeechService(
        tts,  # type: ignore[arg-type]
        store=store or InMemoryConversationStore(),
        publisher=publisher,
        characters_dir=tmp_path / "characters",
    )
    return speech, publisher


async def ready(speech: SpeechService) -> None:
    speech.start_monitor()
    await asyncio.sleep(0.01)


def test_speakable_text_drops_emojis_actions_and_markdown() -> None:
    assert speakable_text("¡Hola, *se ríe* mi amor! 😘❤️ **genial**") == "¡Hola, mi amor! genial"
    assert speakable_text("👋") == ""


@pytest.mark.anyio
async def test_audio_is_regrouped_into_whole_samples_and_closed(
    tmp_path: Path, character_file: Path
) -> None:
    character = make_character(tmp_path, character_file)
    # Odd-sized pieces, as raw HTTP chunks can be: 3 + 9999 + 5 bytes.
    tts = FakeTTS([b"\x01" * 3, b"\x02" * 9999, b"\x03" * 5])
    speech, publisher = make_speech(tmp_path, tts)
    speech.attach_character(character)
    await ready(speech)
    assert speech.will_speak(character)

    speech.start(character, "Hola 😘 *guiña*", utterance_id=1)
    await asyncio.sleep(0.05)

    audio = publisher.of(SpeechAudio)
    sizes = [len(base64.b64decode(a.pcm)) for a in audio]  # type: ignore[attr-defined]
    assert all(size % 2 == 0 for size in sizes)
    assert sum(sizes) == 10006  # the trailing odd byte is dropped, nothing else
    assert [a.seq for a in audio] == list(range(len(audio)))  # type: ignore[attr-defined]
    assert publisher.of(SpeechEnd) == [SpeechEnd(utterance_id=1, ok=True)]
    assert tts.requests == [("testy", "Hola", "Spanish")]
    await speech.aclose()


@pytest.mark.anyio
async def test_failure_still_closes_the_utterance(tmp_path: Path, character_file: Path) -> None:
    character = make_character(tmp_path, character_file)
    speech, publisher = make_speech(tmp_path, FakeTTS([b"\x00" * 10], fail=True))
    await ready(speech)
    speech.start(character, "hola", utterance_id=2)
    await asyncio.sleep(0.05)
    assert publisher.of(SpeechEnd) == [SpeechEnd(utterance_id=2, ok=False)]
    await speech.aclose()


@pytest.mark.anyio
async def test_cancel_stops_mid_sentence(tmp_path: Path, character_file: Path) -> None:
    character = make_character(tmp_path, character_file)
    speech, publisher = make_speech(tmp_path, FakeTTS([b"\x00" * 10000] * 50, delay=0.02))
    await ready(speech)
    speech.start(character, "una frase larga", utterance_id=3)
    await asyncio.sleep(0.07)
    await speech.cancel()
    sent = len(publisher.of(SpeechAudio))
    assert 0 < sent < 50
    assert publisher.of(SpeechEnd) == [SpeechEnd(utterance_id=3, ok=False)]
    await asyncio.sleep(0.05)
    assert len(publisher.of(SpeechAudio)) == sent
    await speech.aclose()


@pytest.mark.anyio
async def test_voice_needs_service_clip_and_toggle(tmp_path: Path, character_file: Path) -> None:
    store = InMemoryConversationStore()
    tts = FakeTTS([])
    tts.ready = False
    speech, publisher = make_speech(tmp_path, tts, store)
    character = make_character(tmp_path, character_file, with_voice=False)
    speech.attach_character(character)
    await ready(speech)
    assert not speech.will_speak(character)  # service not ready

    tts.ready = True
    speech._tts_ready = True
    assert not speech.will_speak(character)  # no voice clip yet
    make_character(tmp_path, character_file, with_voice=True)
    assert speech.will_speak(character)

    await speech.set_enabled(False)
    assert not speech.will_speak(character)
    assert store.get_voice_enabled() is False
    assert publisher.of(VoiceChanged)[-1] == VoiceChanged(available=True, enabled=False)
    await speech.aclose()


@pytest.mark.anyio
async def test_saved_toggle_wins_over_default(tmp_path: Path) -> None:
    store = InMemoryConversationStore()
    store.set_voice_enabled(False)
    speech, _ = make_speech(tmp_path, FakeTTS([]), store)
    assert speech.enabled is False


@pytest.mark.anyio
async def test_reply_announces_voice_and_user_message_interrupts(
    tmp_path: Path, character_file: Path
) -> None:
    character = make_character(tmp_path, character_file)
    tts = FakeTTS([b"\x00" * 10000] * 50, delay=0.02)
    speech, publisher = make_speech(tmp_path, tts)
    await ready(speech)
    service = ConversationService(
        provider=MockAIProvider(0),
        character=character,
        store=InMemoryConversationStore(),
        state=CharacterStateStore(),
        publisher=publisher,
        timeout_seconds=5,
        context_messages=10,
        speech=speech,
    )
    await service.handle_user_message("hola")
    message = publisher.of(AssistantMessage)[0]
    assert message.voice is True  # type: ignore[attr-defined]
    await asyncio.sleep(0.05)
    assert publisher.of(SpeechAudio)

    await service.handle_user_message("espera")  # interrupts the first utterance
    first_id = message.utterance_id  # type: ignore[attr-defined]
    assert SpeechEnd(utterance_id=first_id, ok=False) in publisher.of(SpeechEnd)
    await speech.aclose()


class WindowedProvider(MockAIProvider):
    def __init__(self, window: int) -> None:
        super().__init__(0)
        self.window = window
        self.seen: list[ChatContext] = []

    @property
    def context_window(self) -> int | None:
        return self.window

    async def chat(self, context: ChatContext) -> str:
        self.seen.append(context)
        return await super().chat(context)


@pytest.mark.anyio
async def test_history_is_trimmed_to_fit_the_context_window(character_file: Path) -> None:
    store = InMemoryConversationStore()
    provider: AIProvider = WindowedProvider(window=1500)
    service = ConversationService(
        provider=provider,
        character=Character("testy", CharacterService(load_character_config(character_file))),
        store=store,
        state=CharacterStateStore(),
        publisher=RecordingPublisher(),
        timeout_seconds=5,
        context_messages=100,
    )
    for i in range(30):
        await service.handle_user_message(f"mensaje número {i}: " + "bla " * 40)
        await service.finish_speaking()
    last = provider.seen[-1]  # type: ignore[attr-defined]
    assert len(last.messages) < 59  # older turns were dropped...
    assert last.messages[-1].content.startswith("mensaje número 29")  # ...never the new one
    assert last.messages[-2].role == "assistant"  # and the most recent ones are kept


@pytest.mark.anyio
async def test_tts_client_streams_and_reports_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"ready": True})
        body = json.loads(request.content)
        if body["character_id"] == "nadie":
            return httpx.Response(404, json={"detail": "no voice"})
        return httpx.Response(200, headers={"X-Sample-Rate": "24000"}, content=b"\x00\x01" * 8)

    client = TTSClient("http://tts.test", transport=httpx.MockTransport(handler))
    assert await client.is_ready()
    chunks = [c async for c in client.stream("akari", "hola", "Spanish")]
    assert b"".join(c for _, c in chunks) == b"\x00\x01" * 8
    assert {sr for sr, _ in chunks} == {24000}
    with pytest.raises(TTSUnavailableError):
        async for _ in client.stream("nadie", "hola", "Spanish"):
            pass
    await client.aclose()
