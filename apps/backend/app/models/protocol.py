"""WebSocket protocol. Mirrored in apps/desktop/src/renderer/src/protocol/types.ts.

Both sides validate the shared examples in shared/protocol-fixtures/ in their tests,
so any drift between the TypeScript and Python definitions breaks a test.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

from app.config.settings import PrivacySettings
from app.core.errors import ErrorCode
from app.models.avatar import Emotion, Gesture
from app.models.state import AssistantPhase

PROTOCOL_VERSION = 1

# --- Client -> Server -------------------------------------------------------


class UserMessage(BaseModel):
    type: Literal["user_message"] = "user_message"
    text: str = Field(min_length=1, max_length=4000)


class SpeechFinished(BaseModel):
    """Sent by the client when it finished presenting the assistant's speech."""

    type: Literal["speech_finished"] = "speech_finished"


ClientEvent = Annotated[UserMessage | SpeechFinished, Field(discriminator="type")]
client_event_adapter: TypeAdapter[ClientEvent] = TypeAdapter(ClientEvent)

# --- Server -> Client -------------------------------------------------------


class SessionReady(BaseModel):
    type: Literal["session_ready"] = "session_ready"
    protocol_version: int = PROTOCOL_VERSION
    character_name: str
    ai_provider: str
    ai_is_remote: bool
    privacy: PrivacySettings
    state: AssistantPhase


class StateChanged(BaseModel):
    type: Literal["state_changed"] = "state_changed"
    state: AssistantPhase


class AssistantMessage(BaseModel):
    type: Literal["assistant_message"] = "assistant_message"
    text: str
    emotion: Emotion
    emotion_intensity: float = Field(ge=0.0, le=1.0)
    gesture: Gesture
    look_at_user: bool


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    code: ErrorCode
    message: str


ServerEvent = Annotated[
    SessionReady | StateChanged | AssistantMessage | ErrorEvent,
    Field(discriminator="type"),
]
server_event_adapter: TypeAdapter[ServerEvent] = TypeAdapter(ServerEvent)
