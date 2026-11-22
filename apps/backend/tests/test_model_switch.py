import asyncio
from pathlib import Path

import pytest
from pydantic import BaseModel

from app.ai.base import ChatContext
from app.ai.providers.mock import MockAIProvider
from app.character.config import load_character_config
from app.character.registry import Character
from app.character.service import CharacterService
from app.character.state import CharacterStateStore
from app.conversation.service import ConversationService
from app.core.errors import BusyError, UnknownModelError
from app.memory.store import InMemoryConversationStore
from app.models.protocol import ModelChanged


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[BaseModel] = []

    async def publish(self, event: BaseModel) -> None:
        self.events.append(event)


class SwitchableProvider(MockAIProvider):
    """Mock chat plus Ollama-like model management, recording what happened."""

    def __init__(self, load_seconds: float = 0.0) -> None:
        super().__init__(0)
        self._model = "gpt-oss:latest"
        self.installed = ["gpt-oss:latest", "mistral-nemo:latest", "qwen3:14b"]
        self.log: list[str] = []
        self.models_used: list[str] = []
        self._load_seconds = load_seconds

    @property
    def model(self) -> str:
        return self._model

    async def list_models(self) -> list[str]:
        return self.installed

    async def set_model(self, model: str) -> None:
        self._model = model
        self.log.append(f"set {model}")

    async def unload(self, model: str) -> None:
        self.log.append(f"unload {model}")

    async def warm_up(self) -> None:
        await asyncio.sleep(self._load_seconds)
        self.log.append(f"load {self._model}")

    async def chat(self, context: ChatContext) -> str:
        self.models_used.append(self._model)
        return await super().chat(context)


def make_service(
    provider: SwitchableProvider, character_file: Path, store: InMemoryConversationStore
) -> tuple[ConversationService, RecordingPublisher]:
    publisher = RecordingPublisher()
    service = ConversationService(
        provider=provider,
        character=Character("testy", CharacterService(load_character_config(character_file))),
        store=store,
        state=CharacterStateStore(),
        publisher=publisher,
        timeout_seconds=5,
        context_messages=10,
    )
    return service, publisher


@pytest.mark.anyio
async def test_switch_unloads_old_loads_new_saves_choice_and_keeps_memory(
    character_file: Path,
) -> None:
    provider = SwitchableProvider()
    store = InMemoryConversationStore()
    service, publisher = make_service(provider, character_file, store)
    await service.handle_user_message("me llamo James")

    await service.switch_model("mistral-nemo:latest")

    assert provider.log == [
        "set mistral-nemo:latest",
        "unload gpt-oss:latest",
        "load mistral-nemo:latest",
    ]
    assert store.get_preferred_model() == "mistral-nemo:latest"
    assert [e for e in publisher.events if isinstance(e, ModelChanged)] == [
        ModelChanged(model="mistral-nemo:latest", loading=True),
        ModelChanged(model="mistral-nemo:latest", loading=False),
    ]
    # The conversation is untouched and the new model gets it on the next turn.
    await service.handle_user_message("¿cómo me llamo?")
    assert provider.models_used == ["gpt-oss:latest", "mistral-nemo:latest"]
    assert [m.content for m in store.recent("testy", 10) if m.role == "user"] == [
        "me llamo James",
        "¿cómo me llamo?",
    ]


@pytest.mark.anyio
async def test_only_installed_models_can_be_selected(character_file: Path) -> None:
    provider = SwitchableProvider()
    service, _ = make_service(provider, character_file, InMemoryConversationStore())
    with pytest.raises(UnknownModelError):
        await service.switch_model("llama-malicioso:latest")
    assert provider.model == "gpt-oss:latest"


@pytest.mark.anyio
async def test_messages_wait_while_the_model_loads(character_file: Path) -> None:
    provider = SwitchableProvider(load_seconds=0.2)
    service, _ = make_service(provider, character_file, InMemoryConversationStore())
    switch = asyncio.create_task(service.switch_model("qwen3:14b"))
    await asyncio.sleep(0.05)

    assert service.model_loading
    with pytest.raises(BusyError):
        await service.handle_user_message("hola")
    with pytest.raises(BusyError):
        await service.switch_model("gpt-oss:latest")

    await switch
    assert not service.model_loading
    await service.handle_user_message("hola")


@pytest.mark.anyio
async def test_restore_uses_saved_model_if_still_installed(character_file: Path) -> None:
    store = InMemoryConversationStore()
    store.set_preferred_model("qwen3:14b")
    provider = SwitchableProvider()
    service, _ = make_service(provider, character_file, store)
    await service.restore_model()
    assert provider.model == "qwen3:14b"
    assert provider.log == ["set qwen3:14b", "load qwen3:14b"]


@pytest.mark.anyio
async def test_restore_ignores_a_saved_model_that_was_deleted(character_file: Path) -> None:
    store = InMemoryConversationStore()
    store.set_preferred_model("borrado:latest")
    provider = SwitchableProvider()
    service, _ = make_service(provider, character_file, store)
    await service.restore_model()
    assert provider.model == "gpt-oss:latest"
    assert provider.log == ["load gpt-oss:latest"]
