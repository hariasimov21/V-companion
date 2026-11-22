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
    # Context window in tokens. Persona prompts are long (~6k tokens), and Ollama's
    # default window would silently cut the beginning of the conversation.
    ollama_num_ctx: int = Field(default=16384, ge=2048)

    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    log_level: str = "INFO"

    characters_dir: Path = Path("characters")
    default_character: str = "akari"
    # Messages of the active character's conversation sent to the model on each turn.
    short_term_memory_size: int = Field(default=30, ge=1, le=200)
    # Save conversations to disk (one history per character) so they survive restarts.
    memory_persist: bool = True
    memory_db: Path = Path("data/memory.sqlite3")
    # Long-term memory: facts about the user + summary of what left the recent window.
    long_term_memory_enabled: bool = True
    # Messages folded into long-term memory per update (one extra model call each time).
    memory_batch_messages: int = Field(default=20, ge=2, le=100)

    privacy_microphone_enabled: bool = False
    privacy_camera_enabled: bool = False
    privacy_remote_vision_enabled: bool = False

    @property
    def characters_path(self) -> Path:
        path = self.characters_dir
        return path if path.is_absolute() else REPO_ROOT / path

    @property
    def memory_db_path(self) -> Path:
        path = self.memory_db
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
