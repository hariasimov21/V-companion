import asyncio
import json
from pathlib import Path

import pytest

from app.ai.base import AIProvider, ChatContext, ChatMessage, ImageInput
from app.ai.providers.mock import MockAIProvider
from app.character.config import load_character_config
from app.character.registry import Character
from app.character.service import CharacterService
from app.character.state import CharacterStateStore
from app.conversation.service import ConversationService
from app.core.errors import AIProviderError
from app.memory.long_term import (
    MAX_FACTS,
    MEMORY_UPDATE_SCHEMA,
    MemoryConsolidator,
    _parse,
    render_memory,
)
from app.memory.store import (
    InMemoryConversationStore,
    LongTermMemory,
    SqliteConversationStore,
)


class RecordingPublisher:
    async def publish(self, event: object) -> None:
        pass


class MemoryAwareProvider(AIProvider):
    """Chats like the mock; answers memory updates with a fixed memory (optionally slowly)."""

    name = "fake"
    is_remote = False

    def __init__(self, memory_delay: float = 0.0) -> None:
        self.chats: list[ChatContext] = []
        self.memory_requests: list[ChatContext] = []
        self._mock = MockAIProvider(0)
        self._memory_delay = memory_delay

    async def chat(self, context: ChatContext) -> str:
        if context.response_schema == MEMORY_UPDATE_SCHEMA:
            self.memory_requests.append(context)
            await asyncio.sleep(self._memory_delay)
            return json.dumps({"facts": ["Se llama James."], "summary": "Hablamos de gatos."})
        self.chats.append(context)
        return await self._mock.chat(context)

    async def analyze_image(self, image: ImageInput, prompt: str) -> str:
        return ""


def make_service(
    provider: AIProvider, character_file: Path
) -> tuple[ConversationService, InMemoryConversationStore]:
    store = InMemoryConversationStore()
    service = ConversationService(
        provider=provider,
        character=Character("testy", CharacterService(load_character_config(character_file))),
        store=store,
        state=CharacterStateStore(),
        publisher=RecordingPublisher(),
        timeout_seconds=5,
        context_messages=6,
        consolidator=MemoryConsolidator(provider, timeout_seconds=5),
        memory_batch=2,
    )
    return service, store


async def talk(service: ConversationService, turns: int) -> None:
    for i in range(turns):
        await service.handle_user_message(f"mensaje {i}")
        await service.finish_speaking()


@pytest.mark.anyio
async def test_messages_leaving_the_window_are_folded_into_memory(character_file: Path) -> None:
    provider = MemoryAwareProvider()
    service, store = make_service(provider, character_file)

    await talk(service, 2)  # 4 messages: all inside the window, nothing to fold yet
    assert provider.memory_requests == []

    await talk(service, 1)  # 6 messages: the oldest 2 are about to leave the window
    assert service._consolidation is not None
    await service._consolidation
    request = provider.memory_requests[0].messages[0].content
    assert "User: mensaje 0" in request
    assert "mensaje 1" not in request  # still well inside the window
    memory = store.get_long_term("testy")
    assert memory.facts == ["Se llama James."]
    assert memory.covered_until == 2

    await talk(service, 1)
    system_prompt = provider.chats[-1].system_prompt
    assert "Se llama James." in system_prompt
    assert "Hablamos de gatos." in system_prompt


@pytest.mark.anyio
async def test_forgetting_discards_an_update_in_flight(character_file: Path) -> None:
    provider = MemoryAwareProvider(memory_delay=0.2)
    service, store = make_service(provider, character_file)
    await talk(service, 3)
    assert service._consolidation is not None

    await service.clear_conversation()
    await service._consolidation

    assert store.get_long_term("testy").is_empty


@pytest.mark.anyio
async def test_failed_update_does_not_break_the_chat(character_file: Path) -> None:
    class BrokenMemory(MemoryAwareProvider):
        async def chat(self, context: ChatContext) -> str:
            if context.response_schema == MEMORY_UPDATE_SCHEMA:
                raise AIProviderError("down")
            return await super().chat(context)

    service, store = make_service(BrokenMemory(), character_file)
    await talk(service, 3)
    assert service._consolidation is not None
    await service._consolidation
    assert store.get_long_term("testy").is_empty
    await talk(service, 1)  # still chatting fine


def test_parse_is_lenient_but_bounded() -> None:
    previous = LongTermMemory(["Le gustan los gatos."], "Antes.", 3)
    many = [f"hecho {i}" for i in range(MAX_FACTS + 10)]
    parsed = _parse(
        json.dumps({"facts": ["a", "a", " ", 5, *many], "summary": "x" * 9999}), previous, 9
    )
    assert parsed.facts[:2] == ["a", "hecho 0"]
    assert len(parsed.facts) == MAX_FACTS
    assert len(parsed.summary) < 9999
    assert parsed.covered_until == 9

    lazy = _parse('{"facts": [], "summary": ""}', previous, 9)
    assert lazy.facts == previous.facts  # an empty answer never wipes the memory
    assert lazy.summary == previous.summary

    with pytest.raises(AIProviderError):
        _parse("no json", previous, 9)


def test_render_memory_lists_facts_and_summary() -> None:
    text = render_memory(LongTermMemory(["Se llama James."], "Hablamos de gatos.", 1))
    assert "- Se llama James." in text
    assert "Hablamos de gatos." in text


def test_sqlite_long_term_memory_round_trip_and_clear(tmp_path: Path) -> None:
    for store in (SqliteConversationStore(tmp_path / "m.sqlite3"), InMemoryConversationStore()):
        store.add("akari", [ChatMessage(role="user", content=str(i)) for i in range(5)])
        older = store.older_than_recent("akari", keep_recent=2, after_id=0)
        assert [m.message.content for m in older] == ["0", "1", "2"]
        after = store.older_than_recent("akari", keep_recent=2, after_id=older[0].id)
        assert [m.message.content for m in after] == ["1", "2"]

        store.save_long_term("akari", LongTermMemory(["Se llama José."], "Resumen.", older[-1].id))
        assert store.get_long_term("akari") == LongTermMemory(
            ["Se llama José."], "Resumen.", older[-1].id
        )
        assert store.get_long_term("mimi").is_empty

        store.clear("akari")
        assert store.get_long_term("akari").is_empty
        store.close()
