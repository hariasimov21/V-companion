"""Local TTS HTTP service. Only the backend talks to it, on 127.0.0.1.

    GET  /health -> {"ready": bool, "model": str, "error": str | null}
    POST /speak  {"character_id", "text", "language"} -> streamed raw PCM
         (16-bit little-endian, mono; sample rate in the X-Sample-Rate header)

Engine: qwentts.cpp (GGML, CUDA) running Qwen3-TTS 0.6B Base quantized to 8 bits. Same
voices as the PyTorch version (they sounded identical side by side), ~0.4 GB less VRAM,
6-8x real time instead of ~3x, and no PyTorch install (~250 MB instead of 6.3 GB).

All generation runs on one dedicated thread, one request at a time.
"""

import asyncio
import logging
import os
import queue
import threading
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Any

import numpy as np
import soundfile as sf
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from tts_service.voices import (
    CHARACTER_ID_PATTERN,
    Voice,
    VoiceNotFoundError,
    characters_dir,
    find_voice,
)

log = logging.getLogger("tts")

MODEL = os.environ.get("TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-0.6B-Base")
# Q8_0: indistinguishable from BF16 by ear; Q4_K_M saves only ~0.2 GB more.
QUANT = os.environ.get("TTS_QUANT", "Q8_0")
SAMPLE_RATE = 24000
_END = object()


class SpeakRequest(BaseModel):
    character_id: str = Field(pattern=CHARACTER_ID_PATTERN.pattern)
    text: str = Field(min_length=1, max_length=2000)
    language: str = Field(default="Spanish", max_length=20)


class Engine:
    """Owns the model, the encoded voices and the single generation thread."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tts-gpu")
        self._model: Any = None
        # character id -> encoded reference clip (speaker embedding + codec codes).
        self._voice_refs: dict[str, Any] = {}
        self.error: str | None = None

    @property
    def ready(self) -> bool:
        return self._model is not None

    def start(self) -> None:
        self._executor.submit(self._load)

    def _load(self) -> None:
        try:
            from qwentts_cpp import QwenTTS

            log.info("Loading %s %s (first run downloads it)...", MODEL, QUANT)
            model = QwenTTS.from_pretrained(MODEL, quant=QUANT, log_level="warning")
            self._prepare_voices(model)
            self._model = model
            log.info("TTS ready")
        except Exception as exc:  # pragma: no cover - depends on GPU/model files
            log.exception("Could not load the TTS model")
            self.error = str(exc)[:300]

    def _prepare_voices(self, model: Any) -> None:
        """Encoding a reference clip costs ~1 s: do it for every voice at startup, so
        replies start in ~0.1-0.3 s. A voice added later is encoded on first use."""
        for folder in sorted(characters_dir().iterdir()):
            try:
                voice = find_voice(folder.name)
            except VoiceNotFoundError:
                continue
            self._voice_ref(model, voice)
            log.info("Voice ready: %s", voice.character_id)
        model.synthesize(text="Hola.", lang="spanish")  # warm up the generation path

    def _voice_ref(self, model: Any, voice: Voice) -> Any:
        ref = self._voice_refs.get(voice.character_id)
        if ref is None:
            ref = model.extract_voice_ref(_load_24k(voice))
            self._voice_refs[voice.character_id] = ref
        return ref

    def stream(self, voice: Voice, text: str, language: str) -> AsyncIterator[bytes]:
        """Runs generation on the GPU thread and hands PCM chunks to the event loop."""
        chunks: queue.Queue[object] = queue.Queue(maxsize=8)
        cancelled = threading.Event()

        def produce() -> None:
            try:
                ref = self._voice_ref(self._model, voice)
                for audio, _sr in self._model.stream(
                    text=text,
                    lang=language.lower(),
                    ref_spk_emb=ref.ref_spk_emb,
                    ref_codes=ref.ref_codes,
                    ref_text=voice.ref_text,
                ):
                    if cancelled.is_set():
                        break
                    chunks.put(_to_pcm16(audio))
            except Exception:
                log.exception("Generation failed")
            finally:
                chunks.put(_END)

        self._executor.submit(produce)

        async def iterate() -> AsyncIterator[bytes]:
            try:
                while True:
                    item = await asyncio.to_thread(chunks.get)
                    if item is _END:
                        return
                    assert isinstance(item, bytes)
                    yield item
            finally:
                # The backend hung up (e.g. the user interrupted): stop wasting the GPU.
                cancelled.set()
                _drain(chunks)

        return iterate()


def _load_24k(voice: Voice) -> np.ndarray:
    """The reference clip as mono float32 at 24 kHz, what the model expects."""
    audio, rate = sf.read(voice.ref_audio, dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    if rate == SAMPLE_RATE:
        return np.ascontiguousarray(mono)
    target = np.arange(int(len(mono) * SAMPLE_RATE / rate)) * (rate / SAMPLE_RATE)
    return np.interp(target, np.arange(len(mono)), mono).astype(np.float32)


def _to_pcm16(audio: np.ndarray) -> bytes:
    samples = np.clip(np.asarray(audio, dtype=np.float32).reshape(-1), -1.0, 1.0)
    return (samples * 32767).astype("<i2").tobytes()


def _drain(chunks: "queue.Queue[object]") -> None:
    try:
        while True:
            chunks.get_nowait()
    except queue.Empty:
        pass


def create_app(engine: Engine | None = None) -> FastAPI:
    engine = engine or Engine()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        engine.start()  # loads in the background: /health answers "not ready" meanwhile
        yield

    app = FastAPI(title="Virtual companion TTS", lifespan=lifespan)
    app.state.engine = engine

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {"ready": engine.ready, "model": f"{MODEL} {QUANT}", "error": engine.error}

    @app.post("/speak")
    async def speak(request: SpeakRequest) -> StreamingResponse:
        if not engine.ready:
            raise HTTPException(503, "The TTS model is still loading")
        try:
            voice = find_voice(request.character_id)
        except VoiceNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        return StreamingResponse(
            engine.stream(voice, request.text, request.language),
            media_type="application/octet-stream",
            headers={"X-Sample-Rate": str(SAMPLE_RATE)},
        )

    return app


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [TTS] %(message)s")
    uvicorn.run(
        create_app(),
        host="127.0.0.1",
        port=int(os.environ.get("TTS_PORT", "8010")),
        access_log=False,
    )


if __name__ == "__main__":
    run()
