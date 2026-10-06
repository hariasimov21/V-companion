"""Single source of truth for the character's runtime state.

Phase changes go through `transition_to`, which enforces the allowed transitions and
notifies subscribers (e.g. the WebSocket layer) instead of letting each service keep
its own booleans.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.core.errors import InvalidStateTransition
from app.core.logging import get_logger
from app.models.avatar import Emotion
from app.models.state import AssistantPhase

log = get_logger("state")

P = AssistantPhase
ALLOWED_TRANSITIONS: dict[AssistantPhase, frozenset[AssistantPhase]] = {
    P.IDLE: frozenset({P.LISTENING, P.THINKING}),
    P.LISTENING: frozenset({P.IDLE, P.THINKING}),
    P.THINKING: frozenset({P.SPEAKING, P.ERROR, P.IDLE}),
    # Speaking -> thinking/listening allows the user to interrupt (barge-in).
    P.SPEAKING: frozenset({P.IDLE, P.THINKING, P.LISTENING}),
    P.ERROR: frozenset({P.IDLE, P.THINKING}),
}

PhaseListener = Callable[[AssistantPhase], Awaitable[None]]


@dataclass
class CharacterState:
    phase: AssistantPhase = AssistantPhase.IDLE
    emotion: Emotion = Emotion.NEUTRAL
    is_user_present: bool = False
    last_interaction_at: datetime | None = None


@dataclass
class CharacterStateStore:
    state: CharacterState = field(default_factory=CharacterState)
    _listeners: list[PhaseListener] = field(default_factory=list)

    @property
    def phase(self) -> AssistantPhase:
        return self.state.phase

    def subscribe(self, listener: PhaseListener) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def can_transition_to(self, target: AssistantPhase) -> bool:
        return target in ALLOWED_TRANSITIONS[self.state.phase]

    async def transition_to(self, target: AssistantPhase) -> None:
        current = self.state.phase
        if target == current:
            return
        if not self.can_transition_to(target):
            raise InvalidStateTransition(f"Cannot go from {current} to {target}")
        self.state.phase = target
        log.debug("Phase changed", extra={"fields": {"from": current, "to": target}})
        for listener in list(self._listeners):
            await listener(target)

    def set_emotion(self, emotion: Emotion) -> None:
        self.state.emotion = emotion

    def mark_interaction(self) -> None:
        self.state.last_interaction_at = datetime.now(UTC)
