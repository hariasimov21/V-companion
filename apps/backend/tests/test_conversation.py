import asyncio
from pathlib import Path

import pytest
from pydantic import BaseModel

from app.ai.base import AIProvider, ChatContext, ChatMessage, ImageInput
from app.ai.providers.mock import MockAIProvider
from app.character.config import load_character_config
from app.character.registry import Character
from app.character.service import CharacterService
from app.character.state import CharacterStateStore
from app.conversation.service import ConversationService
from app.core.errors import AIProviderError, AITimeoutError, BusyError
from app.memory.store import InMemoryConversationStore
from app.models.assistant import AssistantReply
from app.models.avatar import Emotion
from app.models.protocol import AssistantMessage, CharacterChanged, ConversationCleared
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
) -> tuple[ConversationService, CharacterStateStore, RecordingPublisher, InMemoryConversationStore]:
    state = CharacterStateStore()
    publisher = RecordingPublisher()
    store = InMemoryConversationStore()
    service = ConversationService(
        provider=provider,
        character=Character("testy", CharacterService(load_character_config(character_file))),
        store=store,
        state=state,
        publisher=publisher,
        timeout_seconds=timeout,
        context_messages=10,
    )
    return service, state, publisher, store


@pytest.mark.anyio
async def test_turn_publishes_reply_and_ends_speaking(character_file: Path) -> None:
    service, state, publisher, memory = make_service(MockAIProvider(0), character_file)

    reply = await service.handle_user_message("¿Funcionas?")

    assert reply.speech == "Hola, estoy funcionando."
    assert reply.emotion is Emotion.HAPPY
    assert state.phase is AssistantPhase.SPEAKING
    assert state.state.emotion is Emotion.HAPPY
    assert isinstance(publisher.events[0], AssistantMessage)
    history = memory.recent("testy", 10)
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
    assert memory.recent("testy", 10) == []


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


@pytest.mark.anyio
async def test_each_character_keeps_its_own_conversation(character_file: Path) -> None:
    service, state, publisher, memory = make_service(MockAIProvider(0), character_file)
    testy = service.character
    await service.handle_user_message("hola")
    other = Character("other", testy.service)

    await service.switch_character(other)

    assert service.character.id == "other"
    assert memory.get_active_character() == "other"
    assert current_phase(state) is AssistantPhase.IDLE
    changed = publisher.events[-1]
    assert isinstance(changed, CharacterChanged)
    assert changed.character_id == "other"
    assert changed.history == []  # never sees testy's conversation

    await service.handle_user_message("¿quién eres?")
    assert memory.recent("other", 10)[0].content == "¿quién eres?"

    await service.switch_character(testy)
    changed = publisher.events[-1]
    assert isinstance(changed, CharacterChanged)
    assert [e.role for e in changed.history] == ["user", "assistant"]
    assert changed.history[0].text == "hola"
    assert changed.history[1].text  # the reply's speech, not its raw JSON
    assert not changed.history[1].text.startswith("{")
    assert changed.history[1].emotion is not None


@pytest.mark.anyio
async def test_context_sent_to_model_is_limited_to_the_window(character_file: Path) -> None:
    seen: list[ChatContext] = []

    class SpyProvider(MockAIProvider):
        async def chat(self, context: ChatContext) -> str:
            seen.append(context)
            return await super().chat(context)

    service, _, _, memory = make_service(SpyProvider(0), character_file)
    for i in range(8):
        await service.handle_user_message(f"mensaje {i}")
        await service.finish_speaking()

    last = seen[-1].messages
    assert len(last) == 11  # 10 remembered messages + the new one
    # The reminder rides inside the latest user message, which comes last.
    assert last[-1].role == "user"
    assert last[-1].content.startswith("mensaje 7\n\n[Instructions for your reply")
    assert "Testy" in last[-1].content
    # It is re-sent each turn, never stored in the conversation.
    assert all("Instructions for your reply" not in m.content for m in memory.recent("testy", 100))
    assert len(service.history()) == 16


@pytest.mark.anyio
async def test_switching_character_while_thinking_is_busy(character_file: Path) -> None:
    service, _, _, _ = make_service(MockAIProvider(0.2), character_file)
    turn = asyncio.create_task(service.handle_user_message("uno"))
    await asyncio.sleep(0.01)
    with pytest.raises(BusyError):
        await service.switch_character(Character("other", service.character.service))
    await turn


@pytest.mark.anyio
async def test_clear_conversation_forgets_only_the_active_character(character_file: Path) -> None:
    service, state, publisher, memory = make_service(MockAIProvider(0), character_file)
    memory.add("other", [ChatMessage(role="user", content="no me borres")])
    await service.handle_user_message("hola")
    assert state.phase is AssistantPhase.SPEAKING

    await service.clear_conversation()

    assert memory.recent("testy", 10) == []
    assert service.history() == []
    assert [m.content for m in memory.recent("other", 10)] == ["no me borres"]
    assert current_phase(state) is AssistantPhase.IDLE
    assert state.state.emotion is Emotion.NEUTRAL
    assert publisher.events[-1] == ConversationCleared(character_id="testy")


@pytest.mark.anyio
async def test_clear_conversation_while_thinking_is_busy(character_file: Path) -> None:
    service, _, _, memory = make_service(MockAIProvider(0.2), character_file)
    turn = asyncio.create_task(service.handle_user_message("uno"))
    await asyncio.sleep(0.01)
    with pytest.raises(BusyError):
        await service.clear_conversation()
    await turn
    assert len(memory.recent("testy", 10)) == 2
