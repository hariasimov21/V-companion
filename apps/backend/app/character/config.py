from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

from app.core.errors import ConfigError


class CharacterIdentity(BaseModel):
    name: str = Field(min_length=1)
    language: str = "es"
    description: str = ""
    speaking_style: str = ""


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


def load_character_config(path: Path) -> CharacterConfig:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return CharacterConfig.model_validate(raw)
    except FileNotFoundError as exc:
        raise ConfigError(f"Character file not found: {path}") from exc
    except (yaml.YAMLError, ValidationError) as exc:
        raise ConfigError(f"Invalid character file {path}: {exc}") from exc
