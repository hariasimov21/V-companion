"""Composition root: the only place where concrete services are wired together."""

from dataclasses import dataclass

from app.ai.base import AIProvider
from app.ai.factory import create_ai_provider
from app.api.connection_manager import ConnectionManager
from app.character.config import load_character_config
from app.character.service import CharacterService
from app.character.state import CharacterStateStore
from app.config.settings import Settings
from app.conversation.service import ConversationService
from app.memory.short_term import ShortTermMemory
from app.models.protocol import StateChanged
from app.models.state import AssistantPhase


@dataclass(frozen=True)
class AppContainer:
    settings: Settings
    provider: AIProvider
    character: CharacterService
    state: CharacterStateStore
    connections: ConnectionManager
    conversation: ConversationService


def build_container(settings: Settings, provider: AIProvider | None = None) -> AppContainer:
    provider = provider or create_ai_provider(settings)
    character = CharacterService(load_character_config(settings.character_path))
    state = CharacterStateStore()
    connections = ConnectionManager()

    async def broadcast_phase(phase: AssistantPhase) -> None:
        await connections.publish(StateChanged(state=phase))

    state.subscribe(broadcast_phase)

    conversation = ConversationService(
        provider=provider,
        character=character,
        memory=ShortTermMemory(settings.short_term_memory_size),
        state=state,
        publisher=connections,
        timeout_seconds=settings.ai_timeout_seconds,
    )
    return AppContainer(settings, provider, character, state, connections, conversation)
