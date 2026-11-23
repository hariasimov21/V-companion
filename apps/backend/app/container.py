"""Composition root: the only place where concrete services are wired together."""

from dataclasses import dataclass

from app.ai.base import AIProvider
from app.ai.factory import create_ai_provider
from app.api.connection_manager import ConnectionManager
from app.character.registry import CharacterRegistry
from app.character.state import CharacterStateStore
from app.config.settings import Settings
from app.conversation.service import ConversationService
from app.memory.long_term import MemoryConsolidator
from app.memory.store import (
    ConversationStore,
    InMemoryConversationStore,
    SqliteConversationStore,
)
from app.models.protocol import StateChanged
from app.models.state import AssistantPhase
from app.speech.service import SpeechService
from app.speech.tts_client import TTSClient


@dataclass(frozen=True)
class AppContainer:
    settings: Settings
    provider: AIProvider
    characters: CharacterRegistry
    state: CharacterStateStore
    connections: ConnectionManager
    store: ConversationStore
    speech: SpeechService
    conversation: ConversationService


def build_container(settings: Settings, provider: AIProvider | None = None) -> AppContainer:
    provider = provider or create_ai_provider(settings)
    characters = CharacterRegistry.load(settings.characters_path, settings.default_character)
    state = CharacterStateStore()
    connections = ConnectionManager()

    async def broadcast_phase(phase: AssistantPhase) -> None:
        await connections.publish(StateChanged(state=phase))

    state.subscribe(broadcast_phase)

    store: ConversationStore = (
        SqliteConversationStore(settings.memory_db_path)
        if settings.memory_persist
        else InMemoryConversationStore()
    )
    # Resume with the character that was active last time (if it still exists).
    active_id = store.get_active_character()
    if active_id not in {c.id for c in characters.all()}:
        active_id = characters.default_id

    speech = SpeechService(
        TTSClient(settings.tts_url),
        store=store,
        publisher=connections,
        characters_dir=settings.characters_path,
        enabled_by_default=settings.voice_enabled,
    )
    speech.attach_character(characters.get(active_id))

    conversation = ConversationService(
        provider=provider,
        character=characters.get(active_id),
        store=store,
        state=state,
        publisher=connections,
        timeout_seconds=settings.ai_timeout_seconds,
        context_messages=settings.short_term_memory_size,
        consolidator=(
            # Summarizing takes longer than a chat reply and nobody is waiting for it.
            MemoryConsolidator(provider, timeout_seconds=max(settings.ai_timeout_seconds, 90))
            if settings.long_term_memory_enabled
            else None
        ),
        memory_batch=settings.memory_batch_messages,
        speech=speech,
    )
    return AppContainer(
        settings, provider, characters, state, connections, store, speech, conversation
    )
