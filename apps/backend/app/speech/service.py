"""Gives the active character a voice: sends each reply to the local TTS service and relays
the audio to the clients as it is generated, so playback starts after ~0.5 s.

Voice is optional at every level: the TTS service may be stopped or still loading, a
character may have no voice clip yet, or the user may have turned it off. In all those
cases replies stay text-only and nothing breaks.
"""

import asyncio
import base64
import contextlib
import itertools
import time
from pathlib import Path
from typing import Protocol

from app.character.registry import Character
from app.core.logging import get_logger
from app.memory.store import ConversationStore
from app.models.protocol import ServerEvent, SpeechAudio, SpeechEnd, VoiceChanged
from app.speech.text import speakable_text
from app.speech.tts_client import TTSClient, TTSUnavailableError

log = get_logger("tts")

# Qwen3-TTS language names for the ISO codes used in character.yaml.
LANGUAGES = {"es": "Spanish", "en": "English", "fr": "French", "de": "German",
             "it": "Italian", "pt": "Portuguese", "ja": "Japanese", "ko": "Korean",
             "zh": "Chinese", "ru": "Russian"}  # fmt: skip
# ~0.2 s of 24 kHz 16-bit audio: fewer, larger WebSocket messages without adding latency.
MIN_CHUNK_BYTES = 9600
HEALTH_POLL_LOADING_S = 3.0
HEALTH_POLL_READY_S = 30.0


class EventPublisher(Protocol):
    async def publish(self, event: ServerEvent) -> None: ...


class SpeechService:
    def __init__(
        self,
        client: TTSClient,
        store: ConversationStore,
        publisher: EventPublisher,
        characters_dir: Path,
        enabled_by_default: bool = True,
    ) -> None:
        self._client = client
        self._store = store
        self._publisher = publisher
        self._characters_dir = characters_dir
        saved = store.get_voice_enabled()
        self._enabled = enabled_by_default if saved is None else saved
        self._tts_ready = False
        self._character: Character | None = None
        self._utterances = itertools.count(1)
        self._current: asyncio.Task[None] | None = None
        self._monitor: asyncio.Task[None] | None = None

    # --- state -------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    def available(self) -> bool:
        """TTS is up and the active character has a voice clip."""
        return self._tts_ready and self._character is not None and self.has_voice(self._character)

    def has_voice(self, character: Character) -> bool:
        folder = self._characters_dir / character.id
        return (folder / "voice.wav").is_file() and (folder / "voice.txt").is_file()

    def will_speak(self, character: Character) -> bool:
        return self._enabled and self._tts_ready and self.has_voice(character)

    def voice_changed_event(self) -> VoiceChanged:
        return VoiceChanged(available=self.available(), enabled=self._enabled)

    def attach_character(self, character: Character) -> None:
        """Initial character, before any client is connected."""
        self._character = character

    async def set_character(self, character: Character) -> None:
        await self.cancel()
        self._character = character
        await self._publisher.publish(self.voice_changed_event())

    async def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self._store.set_voice_enabled(enabled)
        if not enabled:
            await self.cancel()
        await self._publisher.publish(self.voice_changed_event())

    # --- speaking ----------------------------------------------------------

    def next_utterance_id(self) -> int:
        return next(self._utterances)

    def start(self, character: Character, text: str, utterance_id: int) -> None:
        """Speaks in the background: the turn is already delivered as text."""
        self._current = asyncio.create_task(self._speak(character, text, utterance_id))

    async def cancel(self) -> None:
        """Stops the current utterance (the user interrupted or something else took over)."""
        task, self._current = self._current, None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _speak(self, character: Character, text: str, utterance_id: int) -> None:
        language = LANGUAGES.get(character.service.config.character.language, "Auto")
        ok = False
        seq = 0
        pending = b""
        sample_rate = 24000
        audio_bytes = 0
        started = time.monotonic()
        try:
            async for sample_rate, chunk in self._client.stream(
                character.id, speakable_text(text) or "...", language
            ):
                pending += chunk
                audio_bytes += len(chunk)
                # Only whole 16-bit samples, in reasonably sized messages.
                usable = len(pending) - len(pending) % 2
                if usable >= MIN_CHUNK_BYTES:
                    await self._send(utterance_id, seq, sample_rate, pending[:usable])
                    pending, seq = pending[usable:], seq + 1
            if len(pending) >= 2:
                await self._send(utterance_id, seq, sample_rate, pending[: len(pending) // 2 * 2])
            ok = True
            self._log_speed(character, audio_bytes / 2 / sample_rate, time.monotonic() - started)
        except TTSUnavailableError as exc:
            log.warning("Speech failed", extra={"fields": {"error": exc.message}})
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Unexpected speech failure")
        finally:
            # Always close the utterance so the client never waits for audio forever.
            with contextlib.suppress(Exception):
                await asyncio.shield(
                    self._publisher.publish(SpeechEnd(utterance_id=utterance_id, ok=ok))
                )

    @staticmethod
    def _log_speed(character: Character, audio_s: float, elapsed_s: float) -> None:
        if audio_s <= 0 or elapsed_s <= 0:
            return
        speed = audio_s / elapsed_s
        fields = {
            "character": character.id,
            "audio_s": round(audio_s, 1),
            "x_realtime": round(speed, 2),
        }
        if speed < 1.1:
            # Slower than playback: the client runs out of audio and has to pause.
            log.warning(
                "Voice generated slower than real time (GPU memory full?)", extra={"fields": fields}
            )
        else:
            log.info("Speech done", extra={"fields": fields})

    async def _send(self, utterance_id: int, seq: int, sample_rate: int, pcm: bytes) -> None:
        await self._publisher.publish(
            SpeechAudio(
                utterance_id=utterance_id,
                seq=seq,
                sample_rate=sample_rate,
                pcm=base64.b64encode(pcm).decode("ascii"),
            )
        )

    # --- TTS service availability ----------------------------------------------

    def start_monitor(self) -> None:
        self._monitor = asyncio.create_task(self._watch_health())

    async def _watch_health(self) -> None:
        """The TTS model takes ~45 s to load and the service may start after the backend."""
        while True:
            ready = await self._client.is_ready()
            if ready != self._tts_ready:
                self._tts_ready = ready
                log.info("TTS " + ("ready" if ready else "unavailable"))
                await self._publisher.publish(self.voice_changed_event())
            await asyncio.sleep(HEALTH_POLL_READY_S if ready else HEALTH_POLL_LOADING_S)

    async def aclose(self) -> None:
        await self.cancel()
        if self._monitor is not None:
            self._monitor.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitor
        await self._client.aclose()
