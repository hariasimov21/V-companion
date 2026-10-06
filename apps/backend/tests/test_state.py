import pytest

from app.character.state import CharacterStateStore
from app.core.errors import InvalidStateTransition
from app.models.state import AssistantPhase as P


@pytest.mark.anyio
async def test_happy_path_transitions_notify_listeners() -> None:
    store = CharacterStateStore()
    seen: list[P] = []

    async def listener(phase: P) -> None:
        seen.append(phase)

    store.subscribe(listener)
    for phase in (P.THINKING, P.SPEAKING, P.IDLE):
        await store.transition_to(phase)
    assert seen == [P.THINKING, P.SPEAKING, P.IDLE]


@pytest.mark.anyio
async def test_invalid_transition_is_rejected() -> None:
    store = CharacterStateStore()
    with pytest.raises(InvalidStateTransition):
        await store.transition_to(P.SPEAKING)
    assert store.phase is P.IDLE


@pytest.mark.anyio
async def test_same_phase_is_a_no_op() -> None:
    store = CharacterStateStore()
    calls = 0

    async def listener(_: P) -> None:
        nonlocal calls
        calls += 1

    store.subscribe(listener)
    await store.transition_to(P.IDLE)
    assert calls == 0


@pytest.mark.anyio
async def test_unsubscribe_stops_notifications() -> None:
    store = CharacterStateStore()
    seen: list[P] = []

    async def listener(phase: P) -> None:
        seen.append(phase)

    unsubscribe = store.subscribe(listener)
    unsubscribe()
    await store.transition_to(P.THINKING)
    assert seen == []
