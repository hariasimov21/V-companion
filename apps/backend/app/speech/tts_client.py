"""Client for the local TTS service (apps/tts). Audio comes back as streamed raw PCM."""

from collections.abc import AsyncIterator

import httpx

from app.core.errors import AppError, ErrorCode

# Generation streams for as long as the reply lasts; only connecting must be quick.
STREAM_TIMEOUT = httpx.Timeout(120.0, connect=3.0)


class TTSUnavailableError(AppError):
    code = ErrorCode.INTERNAL_ERROR


class TTSClient:
    def __init__(self, base_url: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(5.0, connect=2.0), transport=transport
        )

    async def is_ready(self) -> bool:
        try:
            response = await self._client.get("/health")
            return response.is_success and response.json().get("ready") is True
        except (httpx.HTTPError, ValueError):
            return False

    async def stream(
        self, character_id: str, text: str, language: str
    ) -> AsyncIterator[tuple[int, bytes]]:
        """Yields (sample_rate, pcm16 chunk). Raises TTSUnavailableError on failure."""
        try:
            async with self._client.stream(
                "POST",
                "/speak",
                json={"character_id": character_id, "text": text, "language": language},
                timeout=STREAM_TIMEOUT,
            ) as response:
                if response.is_error:
                    await response.aread()
                    raise TTSUnavailableError(f"TTS error {response.status_code}")
                sample_rate = int(response.headers.get("X-Sample-Rate", "24000"))
                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield sample_rate, chunk
        except httpx.HTTPError as exc:
            raise TTSUnavailableError(f"TTS service unreachable: {exc}") from exc

    async def aclose(self) -> None:
        await self._client.aclose()
