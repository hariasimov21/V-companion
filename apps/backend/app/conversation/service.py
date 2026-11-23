"""Orchestrates one conversational turn: state transitions, AI call, validation, publishing."""

import asyncio
import contextlib
from collections import defaultdict
from typing import Protocol

from pydantic import ValidationError

from app.ai.base import AIProvider, ChatContext, ChatMessage
from app.ai.response_parser import parse_assistant_reply
from app.character.registry import Character
from app.character.state import CharacterStateStore
from app.core.errors import AIProviderError, AITimeoutError, BusyError, UnknownModelError
from app.core.logging import get_logger
from app.memory.long_term import MemoryConsolidator, render_memory
from app.memory.store import ConversationStore, LongTermMemory, StoredMessage
from app.models.assistant import AssistantReply
from app.models.avatar import Emotion
from app.models.protocol import (
    AssistantMessage,
    CharacterChanged,
    ConversationCleared,
    HistoryEntry,
    ModelChanged,
    ServerEvent,
)
from app.models.state import AssistantPhase
from app.speech.service import SpeechService

log = get_logger("ai")

REPLY_SCHEMA = AssistantReply.model_json_schema()
# Rough token estimate for fitting the history into the model's context window. Spanish
# text runs ~3.5-4 characters per token; 3 keeps a safety margin (and JSON replies are
# denser).
CHARS_PER_TOKEN = 3.0
# Room left for the model's own reply (JSON with ~60-140 words of speech).
REPLY_TOKEN_RESERVE = 600
# A first consolidation over a long existing history is split into calls of this size.
MAX_MESSAGES_PER_CONSOLIDATION = 60


class EventPublisher(Protocol):
    async def publish(self, event: ServerEvent) -> None: ...


class ConversationService:
    def __init__(
        self,
        provider: AIProvider,
        character: Character,
        store: ConversationStore,
        state: CharacterStateStore,
        publisher: EventPublisher,
        timeout_seconds: float,
        context_messages: int,
        history_messages: int = 100,
        consolidator: MemoryConsolidator | None = None,
        memory_batch: int = 20,
        speech: SpeechService | None = None,
    ) -> None:
        self._provider = provider
        self._character = character
        self._store = store
        self._context_messages = context_messages
        self._history_messages = history_messages
        self._state = state
        self._publisher = publisher
        self._timeout_seconds = timeout_seconds
        self._turn_lock = asyncio.Lock()
        self._consolidator = consolidator
        self._memory_batch = memory_batch
        self._consolidation: asyncio.Task[None] | None = None
        # Bumped when a conversation is forgotten, so an in-flight update is discarded.
        self._memory_generation: defaultdict[str, int] = defaultdict(int)
        self._model_loading = False
        self._speech = speech

    async def handle_user_message(self, text: str) -> AssistantReply:
        if self._model_loading:
            raise BusyError("The model is still loading")
        if self._turn_lock.locked():
            raise BusyError("Still thinking about the previous message")
        if self._speech is not None:
            await self._speech.cancel()  # the user talking interrupts the character
        async with self._turn_lock:
            character = self._character
            self._state.mark_interaction()
            await self._state.transition_to(AssistantPhase.THINKING)
            try:
                reply = await self._ask_provider(character, text)
            except AIProviderError:
                await self._state.transition_to(AssistantPhase.ERROR)
                raise
            await self._deliver(character, reply)
        self._maybe_consolidate(character)
        return reply

    @property
    def character(self) -> Character:
        return self._character

    def history(self) -> list[HistoryEntry]:
        """The active character's recent conversation, for the client to display."""
        return [
            _to_history_entry(m)
            for m in self._store.recent(self._character.id, self._history_messages)
        ]

    async def switch_character(self, character: Character) -> None:
        """Changes who the user talks to. Each character has its own conversation, so the
        new one resumes where it was left and never sees (or answers as) the previous one."""
        if self._model_loading or self._turn_lock.locked():
            raise BusyError("Wait for the current answer before switching characters")
        async with self._turn_lock:
            if self._speech is not None:
                await self._speech.cancel()  # the previous character stops mid-sentence
            if character.id != self._character.id:
                self._character = character
                self._store.set_active_character(character.id)
                log.info("Character switched", extra={"fields": {"character": character.id}})
            await self._settle_avatar()
            await self._publisher.publish(
                CharacterChanged(
                    character_id=character.id,
                    character_name=character.name,
                    history=self.history(),
                )
            )
            if self._speech is not None:
                await self._speech.set_character(character)  # announces its voice, if any

    async def clear_conversation(self) -> None:
        """Forgets everything said with the active character, on disk too."""
        if self._model_loading or self._turn_lock.locked():
            raise BusyError("Wait for the current answer before clearing the conversation")
        async with self._turn_lock:
            character = self._character
            self._memory_generation[character.id] += 1
            self._store.clear(character.id)
            if self._speech is not None:
                await self._speech.cancel()
            log.info("Conversation cleared", extra={"fields": {"character": character.id}})
            await self._settle_avatar()
            await self._publisher.publish(ConversationCleared(character_id=character.id))

    @property
    def model(self) -> str | None:
        return self._provider.model

    @property
    def model_loading(self) -> bool:
        return self._model_loading

    async def available_models(self) -> list[str]:
        try:
            return await self._provider.list_models()
        except AIProviderError as exc:
            log.warning("Could not list models", extra={"fields": {"error": exc.message}})
            return []

    async def restore_model(self) -> None:
        """At startup: go back to the model chosen last time (if still installed) and load
        it into memory, so the first reply does not pay for the cold start."""
        if self._provider.model is None:  # e.g. the mock: nothing to choose or load
            await self._provider.warm_up()
            return
        async with self._turn_lock:
            preferred = self._store.get_preferred_model()
            if preferred and preferred != self._provider.model:
                if preferred in await self.available_models():
                    await self._provider.set_model(preferred)
                else:
                    log.warning(
                        "Saved model is not installed; using the configured one",
                        extra={"fields": {"model": preferred}},
                    )
            await self._load_model(previous=None)

    async def switch_model(self, model: str) -> None:
        """Changes the model for every character. Conversations and memories are plain text
        in the store, so the new model simply reads them on its next turn."""
        if self._model_loading or self._turn_lock.locked():
            raise BusyError("Wait for the current answer before switching models")
        async with self._turn_lock:
            if model not in await self.available_models():
                raise UnknownModelError(f"Model not installed: {model}")
            previous = self._provider.model
            if model == previous:
                await self._publish_model()
                return
            if self._consolidation is not None and not self._consolidation.done():
                await asyncio.wait([self._consolidation])  # finish it with the old model
            await self._provider.set_model(model)
            self._store.set_preferred_model(model)
            await self._load_model(previous)

    async def _load_model(self, previous: str | None) -> None:
        """Frees the previous model (two rarely fit in VRAM) and loads the current one."""
        self._model_loading = True
        await self._publish_model()
        try:
            if previous and previous != self._provider.model:
                await self._provider.unload(previous)
            await self._provider.warm_up()
        finally:
            self._model_loading = False
            await self._publish_model()

    async def _publish_model(self) -> None:
        if self._provider.model is not None:
            await self._publisher.publish(
                ModelChanged(model=self._provider.model, loading=self._model_loading)
            )

    def long_term_memory(self) -> LongTermMemory:
        return self._store.get_long_term(self._character.id)

    async def aclose(self) -> None:
        if self._consolidation is not None:
            self._consolidation.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._consolidation

    async def finish_speaking(self) -> None:
        if self._state.phase == AssistantPhase.SPEAKING:
            await self._state.transition_to(AssistantPhase.IDLE)

    async def _settle_avatar(self) -> None:
        """Back to a calm idle state, e.g. after a switch or a cleared conversation."""
        if self._state.phase in (AssistantPhase.SPEAKING, AssistantPhase.ERROR):
            await self._state.transition_to(AssistantPhase.IDLE)
        self._state.set_emotion(Emotion.NEUTRAL)

    async def _ask_provider(self, character: Character, text: str) -> AssistantReply:
        user_message = ChatMessage(role="user", content=text)
        system_prompt = character.service.build_system_prompt()
        memory = self._store.get_long_term(character.id)
        if not memory.is_empty:
            # Appended last, so the long static persona prefix stays cacheable by the model.
            system_prompt = f"{system_prompt}\n\n{render_memory(memory)}"
        # The reminder rides inside the latest user turn (and is never stored): chat
        # templates move system messages to the top (gpt-oss, qwen3) or drop them unless a
        # user message comes last (mistral-nemo dropped the whole persona), so this is the
        # only place every model reads it right before answering.
        latest = ChatMessage(
            role="user", content=f"{text}\n\n[{character.service.build_reminder()}]"
        )
        history = self._fit_to_context(
            system_prompt, self._store.recent(character.id, self._context_messages), latest
        )
        context = ChatContext(
            system_prompt=system_prompt,
            messages=[*history, latest],
            response_schema=REPLY_SCHEMA,
        )
        log.info("Request started", extra={"fields": {"provider": self._provider.name}})
        raw = await self._call_with_timeout(context)
        reply = parse_assistant_reply(raw)
        log.info("Response received", extra={"fields": {"emotion": reply.emotion}})

        # Only store the turn once it succeeded, so failed turns don't pollute context.
        # The assistant turn is stored as the full JSON reply: models imitate the history,
        # and plain-text past turns made gpt-oss return empty answers under a JSON schema.
        assistant_message = ChatMessage(role="assistant", content=reply.model_dump_json())
        self._store.add(character.id, [user_message, assistant_message])
        return reply

    def _maybe_consolidate(self, character: Character) -> None:
        """Folds messages about to leave the recent window into long-term memory, in the
        background so the user never waits for it. Folding them slightly before they
        leave means nothing ever falls between the window and the memory."""
        if self._consolidator is None:
            return
        if self._consolidation is not None and not self._consolidation.done():
            return
        memory = self._store.get_long_term(character.id)
        keep_recent = max(self._context_messages - self._memory_batch, 0)
        pending = self._store.older_than_recent(character.id, keep_recent, memory.covered_until)
        if len(pending) < self._memory_batch:
            return
        # Captured now, not when the task starts: a "forget" may run before that.
        generation = self._memory_generation[character.id]
        self._consolidation = asyncio.create_task(
            self._consolidate(
                character, memory, pending[:MAX_MESSAGES_PER_CONSOLIDATION], generation
            )
        )

    async def _consolidate(
        self,
        character: Character,
        memory: LongTermMemory,
        pending: list[StoredMessage],
        generation: int,
    ) -> None:
        assert self._consolidator is not None
        transcript = [(e.role, e.text) for e in (_to_history_entry(m.message) for m in pending)]
        try:
            updated = await self._consolidator.consolidate(
                character.name,
                character.service.config.character.language,
                memory,
                transcript,
                covered_until=pending[-1].id,
            )
        except AIProviderError as exc:
            log.warning("Memory update failed", extra={"fields": {"error": exc.message}})
            return
        except Exception:
            log.exception("Unexpected memory update failure")
            return
        if self._memory_generation[character.id] != generation:
            return  # The conversation was forgotten meanwhile.
        self._store.save_long_term(character.id, updated)
        log.info(
            "Long-term memory updated",
            extra={
                "fields": {
                    "character": character.id,
                    "facts": len(updated.facts),
                    "messages": len(pending),
                }
            },
        )

    async def _call_with_timeout(self, context: ChatContext) -> str:
        try:
            async with asyncio.timeout(self._timeout_seconds):
                return await self._provider.chat(context)
        except TimeoutError as exc:
            log.warning("Request timed out", extra={"fields": {"after_s": self._timeout_seconds}})
            raise AITimeoutError("The AI took too long to answer") from exc
        except AIProviderError as exc:
            log.warning("Provider error", extra={"fields": {"error": exc.message}})
            raise
        except Exception as exc:
            log.exception("Unexpected provider failure")
            raise AIProviderError("Unexpected AI error") from exc

    def _fit_to_context(
        self, system_prompt: str, history: list[ChatMessage], latest: ChatMessage
    ) -> list[ChatMessage]:
        """Drops the oldest messages that would overflow the model's context window.
        Ollama would otherwise cut the *beginning* of the prompt: the persona itself."""
        window = self._provider.context_window
        if window is None:
            return history
        budget = (
            window
            - _estimate_tokens(system_prompt)
            - _estimate_tokens(latest.content)
            - REPLY_TOKEN_RESERVE
        )
        kept: list[ChatMessage] = []
        for message in reversed(history):
            budget -= _estimate_tokens(message.content)
            if budget < 0:
                break
            kept.append(message)
        if len(kept) < len(history):
            log.warning(
                "History trimmed to fit the context window",
                extra={"fields": {"kept": len(kept), "of": len(history), "num_ctx": window}},
            )
        return kept[::-1]

    async def _deliver(self, character: Character, reply: AssistantReply) -> None:
        self._state.set_emotion(reply.emotion)
        speech = self._speech
        voice = speech is not None and speech.will_speak(character)
        utterance_id = speech.next_utterance_id() if speech is not None else 0
        await self._publisher.publish(
            AssistantMessage(
                text=reply.speech,
                emotion=reply.emotion,
                emotion_intensity=reply.emotion_intensity,
                gesture=reply.gesture,
                look_at_user=reply.look_at_user,
                utterance_id=utterance_id,
                voice=voice,
            )
        )
        await self._state.transition_to(AssistantPhase.SPEAKING)
        if voice and speech is not None:
            speech.start(character, reply.speech, utterance_id)


def _estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN) + 4  # + per-message template overhead


def _to_history_entry(message: ChatMessage) -> HistoryEntry:
    if message.role == "user":
        return HistoryEntry(role="user", text=message.content)
    try:
        reply = AssistantReply.model_validate_json(message.content)
    except ValidationError:
        return HistoryEntry(role="assistant", text=message.content)
    return HistoryEntry(
        role="assistant", text=reply.speech, emotion=reply.emotion, gesture=reply.gesture
    )
