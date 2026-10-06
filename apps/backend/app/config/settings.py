from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


class AIProviderName(StrEnum):
    MOCK = "mock"
    OPENAI = "openai"
    OLLAMA = "ollama"


class PrivacySettings(BaseModel):
    microphone_enabled: bool = False
    camera_enabled: bool = False
    remote_vision_enabled: bool = False


class Settings(BaseSettings):
    """Single entry point for environment configuration. Nothing else reads os.environ."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ai_provider: AIProviderName = AIProviderName.MOCK
    ai_timeout_seconds: float = Field(default=30.0, gt=0)

    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = ""
    # Reasoning effort for thinking models: "low" | "medium" | "high" | "true" | "false".
    # Empty = model default.
    ollama_think: str = ""
    # How long Ollama keeps the model in memory after a request (avoids cold starts).
    ollama_keep_alive: str = "30m"

    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    log_level: str = "INFO"

    character_file: Path = Path("character/character.yaml")
    short_term_memory_size: int = Field(default=30, ge=1, le=200)

    privacy_microphone_enabled: bool = False
    privacy_camera_enabled: bool = False
    privacy_remote_vision_enabled: bool = False

    @property
    def character_path(self) -> Path:
        path = self.character_file
        return path if path.is_absolute() else REPO_ROOT / path

    @property
    def privacy(self) -> PrivacySettings:
        return PrivacySettings(
            microphone_enabled=self.privacy_microphone_enabled,
            camera_enabled=self.privacy_camera_enabled,
            remote_vision_enabled=self.privacy_remote_vision_enabled,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
