"""Discovers the characters in characters/<id>/character.yaml."""

import re
from dataclasses import dataclass
from pathlib import Path

from app.character.config import load_character_config
from app.character.service import CharacterService
from app.core.errors import AppError, ConfigError, ErrorCode

CHARACTER_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,63}$"


class UnknownCharacterError(AppError):
    code = ErrorCode.UNKNOWN_CHARACTER


@dataclass(frozen=True)
class Character:
    id: str
    service: CharacterService

    @property
    def name(self) -> str:
        return self.service.name


class CharacterRegistry:
    def __init__(self, characters: list[Character], default_id: str) -> None:
        if not characters:
            raise ConfigError(
                "No characters found: create characters/<id>/character.yaml (see README)"
            )
        self._characters = {c.id: c for c in characters}
        if default_id not in self._characters:
            available = ", ".join(self._characters)
            raise ConfigError(f"Default character '{default_id}' not found (have: {available})")
        self.default_id = default_id

    @classmethod
    def load(cls, directory: Path, default_id: str) -> "CharacterRegistry":
        """Loads every characters/<id>/character.yaml. A broken file fails startup loudly."""
        characters = [
            Character(path.parent.name, CharacterService(load_character_config(path)))
            for path in sorted(directory.glob("*/character.yaml"))
            if re.match(CHARACTER_ID_PATTERN, path.parent.name)
        ]
        return cls(characters, default_id)

    def get(self, character_id: str) -> Character:
        try:
            return self._characters[character_id]
        except KeyError:
            raise UnknownCharacterError(f"Unknown character: {character_id}") from None

    def all(self) -> list[Character]:
        return list(self._characters.values())
