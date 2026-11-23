"""Finds each character's voice: characters/<id>/voice.wav plus its transcript voice.txt.

The reference clip is what Qwen3-TTS clones. It is usually designed once with
`make voice CHARACTER=<id>` (see design.py) and then reused for every reply, so the
character always sounds the same.
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHARACTER_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
# Qwen3-TTS language names for the ISO codes used in character.yaml.
LANGUAGES = {
    "es": "Spanish",
    "en": "English",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ru": "Russian",
}


class VoiceNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class Voice:
    character_id: str
    ref_audio: Path
    ref_text: str


def characters_dir() -> Path:
    """Same folder (and the same CHARACTERS_DIR setting) the backend uses."""
    configured = Path(os.environ.get("CHARACTERS_DIR", "characters"))
    return configured if configured.is_absolute() else REPO_ROOT / configured


def find_voice(character_id: str, root: Path | None = None) -> Voice:
    if not CHARACTER_ID_PATTERN.match(character_id):
        raise VoiceNotFoundError(f"Invalid character id: {character_id!r}")
    folder = (root or characters_dir()) / character_id
    audio, text = folder / "voice.wav", folder / "voice.txt"
    if not audio.is_file() or not text.is_file():
        raise VoiceNotFoundError(
            f"{character_id} has no voice yet: run make voice CHARACTER={character_id}"
        )
    return Voice(character_id, audio, text.read_text(encoding="utf-8").strip())


def language_name(code: str) -> str:
    return LANGUAGES.get(code.lower(), "Auto")
