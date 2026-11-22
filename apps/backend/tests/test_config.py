from pathlib import Path

import pytest
from pydantic import SecretStr

from app.ai.factory import create_ai_provider
from app.ai.providers.mock import MockAIProvider
from app.character.config import load_character_config
from app.character.registry import CharacterRegistry, UnknownCharacterError
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


def test_relative_characters_dir_resolves_from_repo_root(settings: Settings) -> None:
    assert settings.characters_path == REPO_ROOT / "characters"


def test_factory_builds_mock_provider(settings: Settings) -> None:
    assert isinstance(create_ai_provider(settings), MockAIProvider)


def test_factory_requires_openai_key() -> None:
    settings = Settings(_env_file=None, ai_provider=AIProviderName.OPENAI)
    with pytest.raises(ConfigError):
        create_ai_provider(settings)


def test_local_characters_are_valid(settings: Settings) -> None:
    # characters/ is personal (gitignored): validate it when present, skip on a clean clone.
    if not settings.characters_path.is_dir():
        pytest.skip("no local characters/ folder")
    registry = CharacterRegistry.load(settings.characters_path, settings.default_character)
    for character in registry.all():
        assert character.name
        assert character.service.build_system_prompt()


def test_registry_loads_characters_by_folder(characters_dir: Path) -> None:
    registry = CharacterRegistry.load(characters_dir, "testy")
    assert [c.id for c in registry.all()] == ["other", "testy"]
    assert registry.get("other").name == "Other"
    with pytest.raises(UnknownCharacterError):
        registry.get("missing")


def test_registry_requires_existing_default(characters_dir: Path) -> None:
    with pytest.raises(ConfigError):
        CharacterRegistry.load(characters_dir, "missing")


def test_prompt_file_replaces_generated_persona(characters_dir: Path) -> None:
    config = load_character_config(characters_dir / "other" / "character.yaml")
    prompt = CharacterService(config).build_system_prompt()
    assert prompt.startswith("# OTHER\nEres Other.")
    assert "Personality:" not in prompt
    assert "camera and microphone are OFF" in prompt
    assert "Respond ONLY with a JSON object" in prompt


def test_prompt_file_cannot_escape_character_folder(tmp_path: Path) -> None:
    (tmp_path / "secret.txt").write_text("nope", encoding="utf-8")
    folder = tmp_path / "evil"
    folder.mkdir()
    path = folder / "character.yaml"
    path.write_text("character:\n  name: Evil\n  prompt_file: ../secret.txt\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_character_config(path)


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


def test_reply_length_shapes_format_and_reminder(tmp_path: Path) -> None:
    path = tmp_path / "character.yaml"
    path.write_text(
        "character:\n  name: Testy\n  description: Gata sarcástica\n  reply_length: long\n",
        encoding="utf-8",
    )
    service = CharacterService(load_character_config(path))
    assert "4-6 sentences" in service.build_system_prompt()
    reminder = service.build_reminder()
    assert "you are Testy (Gata sarcástica)" in reminder
    assert "4-6 sentences" in reminder
    assert "short" not in service.build_system_prompt().split("Respond ONLY")[1]


def test_reply_length_defaults_to_medium(character_file: Path) -> None:
    service = CharacterService(load_character_config(character_file))
    assert "2-4 sentences" in service.build_reminder()
