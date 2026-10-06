import asyncio
from pathlib import Path

import pytest
from pydantic import BaseModel

from app.ai.base import AIProvider, ChatContext, ImageInput
from app.ai.providers.mock import MockAIProvider
from app.character.config import load_character_config
from app.character.service import CharacterService
from app.character.state import CharacterStateStore
from app.conversation.service import ConversationService
from app.core.errors import AIProviderError, AITimeoutError, BusyError
from app.memory.short_term import ShortTermMemory
from app.models.assistant import AssistantReply
from app.models.avatar import Emotion
from app.models.protocol import AssistantMessage
from app.models.state import AssistantPhase


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[BaseModel] = []

    async def publish(self, event: BaseModel) -> None:
        self.events.append(event)


class SlowProvider(AIProvider):
    name = "slow"
    is_remote = False

    async def chat(self, context: ChatContext) -> str:
        await asyncio.sleep(10)
        return "{}"

    async def analyze_image(self, image: ImageInput, prompt: str) -> str:
        return ""


class CrashingProvider(SlowProvider):
    async def chat(self, context: ChatContext) -> str:
        raise RuntimeError("boom")


def current_phase(state: CharacterStateStore) -> AssistantPhase:
    """Re-reads the phase; avoids mypy keeping a narrowed type across awaits."""
    return state.phase


def make_service(
    provider: AIProvider, character_file: Path, timeout: float = 5.0
) -> tuple[ConversationService, CharacterStateStore, RecordingPublisher, ShortTermMemory]:
    state = CharacterStateStore()
    publisher = RecordingPublisher()
    memory = ShortTermMemory(10)
    service = ConversationService(
        provider=provider,
        character=CharacterService(load_character_config(character_file)),
        memory=memory,
        state=state,
        publisher=publisher,
        timeout_seconds=timeout,
    )
    return service, state, publisher, memory


@pytest.mark.anyio
async def test_turn_publishes_reply_and_ends_speaking(character_file: Path) -> None:
    service, state, publisher, memory = make_service(MockAIProvider(0), character_file)

    reply = await service.handle_user_message("¿Funcionas?")

    assert reply.speech == "Hola, estoy funcionando."
    assert reply.emotion is Emotion.HAPPY
    assert state.phase is AssistantPhase.SPEAKING
    assert state.state.emotion is Emotion.HAPPY
    assert isinstance(publisher.events[0], AssistantMessage)
    history = memory.get_recent_context()
    assert [m.role for m in history] == ["user", "assistant"]
    assert AssistantReply.model_validate_json(history[1].content) == reply

    await service.finish_speaking()
    assert current_phase(state) is AssistantPhase.IDLE


@pytest.mark.anyio
async def test_provider_error_moves_to_error_state(character_file: Path) -> None:
    service, state, publisher, memory = make_service(MockAIProvider(0), character_file)

    with pytest.raises(AIProviderError):
        await service.handle_user_message("/error")

    assert state.phase is AssistantPhase.ERROR
    assert publisher.events == []
    assert memory.get_recent_context() == []


@pytest.mark.anyio
async def test_timeout_raises_ai_timeout(character_file: Path) -> None:
    service, state, _, _ = make_service(SlowProvider(), character_file, timeout=0.05)
    with pytest.raises(AITimeoutError):
        await service.handle_user_message("hola")
    assert state.phase is AssistantPhase.ERROR


@pytest.mark.anyio
async def test_unexpected_exception_is_wrapped(character_file: Path) -> None:
    service, _, _, _ = make_service(CrashingProvider(), character_file)
    with pytest.raises(AIProviderError):
        await service.handle_user_message("hola")


@pytest.mark.anyio
async def test_recovers_after_error(character_file: Path) -> None:
    service, state, _, _ = make_service(MockAIProvider(0), character_file)
    with pytest.raises(AIProviderError):
        await service.handle_user_message("/error")
    await service.handle_user_message("hola")
    assert state.phase is AssistantPhase.SPEAKING


@pytest.mark.anyio
async def test_concurrent_message_is_rejected_as_busy(character_file: Path) -> None:
    service, _, _, _ = make_service(MockAIProvider(0.2), character_file)
    first = asyncio.create_task(service.handle_user_message("uno"))
    await asyncio.sleep(0.01)
    with pytest.raises(BusyError):
        await service.handle_user_message("dos")
    await first
