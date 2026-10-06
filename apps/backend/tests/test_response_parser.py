import json

from app.ai.response_parser import FALLBACK_SPEECH, parse_assistant_reply
from app.models.avatar import Emotion, Gesture


def test_parses_well_formed_reply() -> None:
    raw = json.dumps(
        {
            "speech": "¡Eso quedó muy bien!",
            "emotion": "happy",
            "emotion_intensity": 0.75,
            "gesture": "nod",
            "look_at_user": True,
        }
    )
    reply = parse_assistant_reply(raw)
    assert reply.speech == "¡Eso quedó muy bien!"
    assert reply.emotion is Emotion.HAPPY
    assert reply.emotion_intensity == 0.75
    assert reply.gesture is Gesture.NOD
    assert reply.look_at_user is True


def test_extracts_json_wrapped_in_code_fences_and_prose() -> None:
    raw = 'Claro:\n```json\n{"speech": "Hola", "emotion": "curious"}\n```'
    reply = parse_assistant_reply(raw)
    assert reply.speech == "Hola"
    assert reply.emotion is Emotion.CURIOUS


def test_invalid_fields_fall_back_to_safe_defaults() -> None:
    raw = json.dumps(
        {
            "speech": "Hola",
            "emotion": "furious",
            "emotion_intensity": "very",
            "gesture": "backflip",
            "look_at_user": "yes",
        }
    )
    reply = parse_assistant_reply(raw)
    assert reply.emotion is Emotion.NEUTRAL
    assert reply.emotion_intensity == 0.5
    assert reply.gesture is Gesture.NONE
    assert reply.look_at_user is True


def test_intensity_is_clamped() -> None:
    assert parse_assistant_reply('{"speech": "a", "emotion_intensity": 7}').emotion_intensity == 1.0
    assert (
        parse_assistant_reply('{"speech": "a", "emotion_intensity": -2}').emotion_intensity == 0.0
    )


def test_enum_values_are_normalized() -> None:
    reply = parse_assistant_reply('{"speech": "a", "emotion": " Happy ", "gesture": "WAVE"}')
    assert reply.emotion is Emotion.HAPPY
    assert reply.gesture is Gesture.WAVE


def test_plain_text_becomes_speech() -> None:
    reply = parse_assistant_reply("Solo texto, sin JSON.")
    assert reply.speech == "Solo texto, sin JSON."
    assert reply.emotion is Emotion.NEUTRAL


def test_empty_or_missing_speech_uses_fallback() -> None:
    assert parse_assistant_reply("").speech == FALLBACK_SPEECH
    assert parse_assistant_reply('{"emotion": "sad"}').speech == FALLBACK_SPEECH
    assert parse_assistant_reply("[1, 2, 3]").speech == "[1, 2, 3]"
