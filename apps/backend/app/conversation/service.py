"""Orchestrates one conversational turn: state transitions, AI call, validation, publishing."""

import asyncio
from typing import Protocol

from app.ai.base import AIProvider, ChatContext, ChatMessage
from app.ai.response_parser import parse_assistant_reply
from app.character.service import CharacterService
from app.character.state import CharacterStateStore
from app.core.errors import AIProviderError, AITimeoutError, BusyError
from app.core.logging import get_logger
from app.memory.short_term import ShortTermMemory
from app.models.assistant import AssistantReply
from app.models.protocol import AssistantMessage, ServerEvent
from app.models.state import AssistantPhase

log = get_logger("ai")

REPLY_SCHEMA = AssistantReply.model_json_schema()


class EventPublisher(Protocol):
    async def publish(self, event: ServerEvent) -> None: ...


class ConversationService:
    def __init__(
        self,
        provider: AIProvider,
        character: CharacterService,
        memory: ShortTermMemory,
        state: CharacterStateStore,
        publisher: EventPublisher,
        timeout_seconds: float,
    ) -> None:
        self._provider = provider
        self._character = character
        self._memory = memory
        self._state = state
        self._publisher = publisher
        self._timeout_seconds = timeout_seconds
        self._turn_lock = asyncio.Lock()

    async def handle_user_message(self, text: str) -> AssistantReply:
        if self._turn_lock.locked():
            raise BusyError("Still thinking about the previous message")
        async with self._turn_lock:
            self._state.mark_interaction()
            await self._state.transition_to(AssistantPhase.THINKING)
            try:
                reply = await self._ask_provider(text)
            except AIProviderError:
                await self._state.transition_to(AssistantPhase.ERROR)
                raise
            await self._deliver(reply)
            return reply

    async def finish_speaking(self) -> None:
        if self._state.phase == AssistantPhase.SPEAKING:
            await self._state.transition_to(AssistantPhase.IDLE)

    async def _ask_provider(self, text: str) -> AssistantReply:
        user_message = ChatMessage(role="user", content=text)
        context = ChatContext(
            system_prompt=self._character.build_system_prompt(),
            messages=[*self._memory.get_recent_context(), user_message],
            response_schema=REPLY_SCHEMA,
        )
        log.info("Request started", extra={"fields": {"provider": self._provider.name}})
        raw = await self._call_with_timeout(context)
        reply = parse_assistant_reply(raw)
        log.info("Response received", extra={"fields": {"emotion": reply.emotion}})

        # Only store the turn once it succeeded, so failed turns don't pollute context.
        # The assistant turn is stored as the full JSON reply: models imitate the history,
        # and plain-text past turns made gpt-oss return empty answers under a JSON schema.
        self._memory.add(user_message)
        self._memory.add(ChatMessage(role="assistant", content=reply.model_dump_json()))
        return reply

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

    async def _deliver(self, reply: AssistantReply) -> None:
        self._state.set_emotion(reply.emotion)
        await self._publisher.publish(
            AssistantMessage(
                text=reply.speech,
                emotion=reply.emotion,
                emotion_intensity=reply.emotion_intensity,
                gesture=reply.gesture,
                look_at_user=reply.look_at_user,
            )
        )
        await self._state.transition_to(AssistantPhase.SPEAKING)
