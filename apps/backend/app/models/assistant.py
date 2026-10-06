from pydantic import BaseModel, Field

from app.models.avatar import Emotion, Gesture


class AssistantReply(BaseModel):
    """Validated, semantic reply produced by the AI layer. Never sent raw from the model."""

    speech: str = Field(min_length=1)
    emotion: Emotion = Emotion.NEUTRAL
    emotion_intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    gesture: Gesture = Gesture.NONE
    look_at_user: bool = True
