"""Turns untrusted model output into a valid `AssistantReply`.

Models sometimes wrap JSON in code fences, add prose, or invent enum values. Instead of
failing the whole turn, each field is salvaged individually and falls back to a safe
default.
"""

import json
from typing import Any

from app.core.logging import get_logger
from app.models.assistant import AssistantReply
from app.models.avatar import Emotion, Gesture

log = get_logger("ai")

FALLBACK_SPEECH = "..."
DEFAULT_INTENSITY = 0.5


def parse_assistant_reply(raw: str) -> AssistantReply:
    data = _extract_json_object(raw)
    if data is None:
        text = raw.strip()
        if text:
            log.warning("Model returned non-JSON output; using it as plain speech")
        return AssistantReply(speech=text or FALLBACK_SPEECH)

    return AssistantReply(
        speech=_parse_speech(data.get("speech")),
        emotion=_parse_enum(Emotion, data.get("emotion"), Emotion.NEUTRAL),
        emotion_intensity=_parse_intensity(data.get("emotion_intensity")),
        gesture=_parse_enum(Gesture, data.get("gesture"), Gesture.NONE),
        look_at_user=_parse_bool(data.get("look_at_user"), default=True),
    )


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse_speech(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return FALLBACK_SPEECH


def _parse_enum[E: (Emotion, Gesture)](enum_type: type[E], value: object, default: E) -> E:
    if isinstance(value, str):
        try:
            return enum_type(value.strip().lower())
        except ValueError:
            log.warning(
                "Unknown enum value from model",
                extra={"fields": {"enum": enum_type.__name__, "value": value}},
            )
    return default


def _parse_bool(value: object, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _parse_intensity(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return DEFAULT_INTENSITY
    return min(max(float(value), 0.0), 1.0)
