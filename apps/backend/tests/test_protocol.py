import pytest
from pydantic import ValidationError

from app.models.protocol import client_event_adapter, server_event_adapter
from tests.conftest import load_fixture


@pytest.mark.parametrize("event", load_fixture("server-events.valid.json"))
def test_valid_server_events_are_accepted(event: dict[str, object]) -> None:
    parsed = server_event_adapter.validate_python(event)
    assert parsed.type == event["type"]


@pytest.mark.parametrize("event", load_fixture("server-events.invalid.json"))
def test_invalid_server_events_are_rejected(event: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        server_event_adapter.validate_python(event)


@pytest.mark.parametrize("event", load_fixture("client-events.valid.json"))
def test_valid_client_events_are_accepted(event: dict[str, object]) -> None:
    parsed = client_event_adapter.validate_python(event)
    assert parsed.type == event["type"]


@pytest.mark.parametrize("event", load_fixture("client-events.invalid.json"))
def test_invalid_client_events_are_rejected(event: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        client_event_adapter.validate_python(event)


def test_server_event_round_trips_through_json() -> None:
    original = server_event_adapter.validate_python(load_fixture("server-events.valid.json")[2])
    serialized = original.model_dump_json()
    assert server_event_adapter.validate_json(serialized) == original
