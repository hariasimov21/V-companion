from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

from app.core.errors import ConfigError


class ReplyLength(StrEnum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class CharacterIdentity(BaseModel):
    name: str = Field(min_length=1)
    language: str = "es"
    description: str = ""
    speaking_style: str = ""
    # Optional Markdown/text file (relative to character.yaml) with the full persona prompt.
    prompt_file: str | None = None
    # How much the character says per reply (spoken text, so even "long" stays a few lines).
    reply_length: ReplyLength = ReplyLength.MEDIUM


class Personality(BaseModel):
    affectionate: float = Field(default=0.5, ge=0.0, le=1.0)
    curiosity: float = Field(default=0.5, ge=0.0, le=1.0)
    humor: float = Field(default=0.5, ge=0.0, le=1.0)
    sarcasm: float = Field(default=0.0, ge=0.0, le=1.0)
    energy: float = Field(default=0.5, ge=0.0, le=1.0)
    assertiveness: float = Field(default=0.5, ge=0.0, le=1.0)


class Behavior(BaseModel):
    proactive: bool = False
    interrupt_probability: float = Field(default=0.0, ge=0.0, le=1.0)


class Proactivity(BaseModel):
    enabled: bool = False
    minimum_interval_seconds: int = Field(default=300, ge=0)
    probability: float = Field(default=0.0, ge=0.0, le=1.0)


class CharacterConfig(BaseModel):
    character: CharacterIdentity
    personality: Personality = Personality()
    behavior: Behavior = Behavior()
    proactivity: Proactivity = Proactivity()
    # Contents of `character.prompt_file`, filled in by load_character_config.
    persona_prompt: str = ""


def load_character_config(path: Path) -> CharacterConfig:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        config = CharacterConfig.model_validate(raw)
    except FileNotFoundError as exc:
        raise ConfigError(f"Character file not found: {path}") from exc
    except (yaml.YAMLError, ValidationError) as exc:
        raise ConfigError(f"Invalid character file {path}: {exc}") from exc

    prompt_file = config.character.prompt_file
    if prompt_file:
        prompt_path = (path.parent / prompt_file).resolve()
        if not prompt_path.is_relative_to(path.parent.resolve()):
            raise ConfigError(f"prompt_file must stay inside the character folder: {path}")
        try:
            config.persona_prompt = prompt_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError as exc:
            raise ConfigError(f"Prompt file not found: {prompt_path}") from exc
    return config
