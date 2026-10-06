from pathlib import Path

import pytest
from pydantic import SecretStr

from app.ai.factory import create_ai_provider
from app.ai.providers.mock import MockAIProvider
from app.character.config import load_character_config
from app.character.service import CharacterService
from app.config.settings import REPO_ROOT, AIProviderName, Settings
from app.core.errors import ConfigError


def test_defaults_are_private_and_offline(settings: Settings) -> None:
    assert settings.ai_provider is AIProviderName.MOCK
    assert settings.privacy.microphone_enabled is False
    assert settings.privacy.camera_enabled is False
    assert settings.privacy.remote_vision_enabled is False


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    monkeypatch.setenv("PRIVACY_CAMERA_ENABLED", "true")
    settings = Settings(_env_file=None)
    assert settings.ai_provider is AIProviderName.OLLAMA
    assert settings.privacy.camera_enabled is True


def test_api_key_is_never_rendered() -> None:
    settings = Settings(_env_file=None, openai_api_key=SecretStr("sk-secret"))
    assert "sk-secret" not in repr(settings)
    assert "sk-secret" not in str(settings.model_dump())


def test_relative_character_path_resolves_from_repo_root(settings: Settings) -> None:
    assert settings.character_path == REPO_ROOT / "character" / "character.yaml"


def test_factory_builds_mock_provider(settings: Settings) -> None:
    assert isinstance(create_ai_provider(settings), MockAIProvider)


def test_factory_requires_openai_key() -> None:
    settings = Settings(_env_file=None, ai_provider=AIProviderName.OPENAI)
    with pytest.raises(ConfigError):
        create_ai_provider(settings)


def test_repository_character_file_is_valid(settings: Settings) -> None:
    config = load_character_config(settings.character_path)
    assert config.character.name


def test_invalid_character_file_raises_config_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("personality:\n  humor: 5\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_character_config(path)


def test_system_prompt_is_built_from_config(character_file: Path) -> None:
    prompt = CharacterService(load_character_config(character_file)).build_system_prompt()
    assert "Testy" in prompt
    assert "extremely curious" in prompt
    assert "never sarcastic" in prompt
    assert "thinking" in prompt  # emotion list
    assert "shake_head" in prompt  # gesture list
