"""WebSocket protocol. Mirrored in apps/desktop/src/renderer/src/protocol/types.ts.

Both sides validate the shared examples in shared/protocol-fixtures/ in their tests,
so any drift between the TypeScript and Python definitions breaks a test.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StrictBool, TypeAdapter

from app.character.registry import CHARACTER_ID_PATTERN
from app.config.settings import PrivacySettings
from app.core.errors import ErrorCode
from app.models.avatar import Emotion, Gesture
from app.models.state import AssistantPhase

PROTOCOL_VERSION = 5
# Ollama model names, e.g. "qwen3:14b" or "hf.co/user/repo:Q4_K_M".
MODEL_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$"

# --- Client -> Server -------------------------------------------------------


class UserMessage(BaseModel):
    type: Literal["user_message"] = "user_message"
    text: str = Field(min_length=1, max_length=4000)


class SpeechFinished(BaseModel):
    """Sent by the client when it finished presenting the assistant's speech."""

    type: Literal["speech_finished"] = "speech_finished"


class SelectCharacter(BaseModel):
    """Switches the active character; its own saved conversation is resumed."""

    type: Literal["select_character"] = "select_character"
    character_id: str = Field(pattern=CHARACTER_ID_PATTERN)


class ClearConversation(BaseModel):
    """Forgets the active character's whole conversation (cannot be undone)."""

    type: Literal["clear_conversation"] = "clear_conversation"


class SelectModel(BaseModel):
    """Switches the AI model for every character. Only installed local models."""

    type: Literal["select_model"] = "select_model"
    model: str = Field(pattern=MODEL_NAME_PATTERN)


class SetVoice(BaseModel):
    """Turns the character's spoken voice on or off (remembered across restarts)."""

    type: Literal["set_voice"] = "set_voice"
    enabled: StrictBool


ClientEvent = Annotated[
    UserMessage | SpeechFinished | SelectCharacter | ClearConversation | SelectModel | SetVoice,
    Field(discriminator="type"),
]
client_event_adapter: TypeAdapter[ClientEvent] = TypeAdapter(ClientEvent)

# --- Server -> Client -------------------------------------------------------


class CharacterSummary(BaseModel):
    id: str
    name: str


class HistoryEntry(BaseModel):
    """A past chat message, so the client can show a resumed conversation."""

    role: Literal["user", "assistant"]
    text: str
    emotion: Emotion | None = None
    gesture: Gesture | None = None


class SessionReady(BaseModel):
    type: Literal["session_ready"] = "session_ready"
    protocol_version: int = PROTOCOL_VERSION
    character_id: str
    character_name: str
    characters: list[CharacterSummary]
    history: list[HistoryEntry]
    ai_provider: str
    ai_is_remote: bool
    # Model in use and the ones the user can switch to (empty = not switchable).
    ai_model: str | None
    ai_models: list[str]
    ai_model_loading: bool
    # Voice: `available` = TTS service ready and the active character has a voice.
    voice_available: bool
    voice_enabled: bool
    privacy: PrivacySettings
    state: AssistantPhase


class CharacterChanged(BaseModel):
    """Broadcast after a switch; clients replace the chat with `history` and swap the avatar."""

    type: Literal["character_changed"] = "character_changed"
    character_id: str
    character_name: str
    history: list[HistoryEntry]


class ConversationCleared(BaseModel):
    """Broadcast after a character's conversation was forgotten; clients empty the chat."""

    type: Literal["conversation_cleared"] = "conversation_cleared"
    character_id: str


class ModelChanged(BaseModel):
    """Broadcast when the model changes: first while it loads, then once it is ready."""

    type: Literal["model_changed"] = "model_changed"
    model: str
    loading: bool


class SpeechAudio(BaseModel):
    """A piece of the spoken reply: base64 PCM, 16-bit little-endian, mono."""

    type: Literal["speech_audio"] = "speech_audio"
    utterance_id: int
    seq: int = Field(ge=0)
    sample_rate: int = Field(gt=0)
    pcm: str


class SpeechEnd(BaseModel):
    """No more audio for this utterance (`ok` false: it failed or was cut short)."""

    type: Literal["speech_end"] = "speech_end"
    utterance_id: int
    ok: bool


class VoiceChanged(BaseModel):
    type: Literal["voice_changed"] = "voice_changed"
    available: bool
    enabled: bool


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
    # When `voice` is true, speech_audio chunks for `utterance_id` follow, then speech_end.
    utterance_id: int
    voice: bool


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    code: ErrorCode
    message: str


ServerEvent = Annotated[
    SessionReady
    | CharacterChanged
    | ConversationCleared
    | ModelChanged
    | SpeechAudio
    | SpeechEnd
    | VoiceChanged
    | StateChanged
    | AssistantMessage
    | ErrorEvent,
    Field(discriminator="type"),
]
server_event_adapter: TypeAdapter[ServerEvent] = TypeAdapter(ServerEvent)
