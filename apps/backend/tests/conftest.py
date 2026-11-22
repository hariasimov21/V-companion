import json
from pathlib import Path
from typing import Any

import pytest

from app.config.settings import REPO_ROOT, Settings

FIXTURES_DIR = REPO_ROOT / "shared" / "protocol-fixtures"


def load_fixture(name: str) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    return data


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings() -> Settings:
    # _env_file=None keeps a developer's local .env out of the tests.
    return Settings(_env_file=None)


@pytest.fixture
def character_file(tmp_path: Path) -> Path:
    path = tmp_path / "character.yaml"
    path.write_text(
        "character:\n  name: Testy\n  language: es\n"
        "personality:\n  curiosity: 0.9\n  sarcasm: 0.1\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def characters_dir(tmp_path: Path) -> Path:
    """Two characters: one with generated persona, one with a prompt file."""
    root = tmp_path / "characters"
    (root / "testy").mkdir(parents=True)
    (root / "testy" / "character.yaml").write_text("character:\n  name: Testy\n", encoding="utf-8")
    (root / "other").mkdir()
    (root / "other" / "character.yaml").write_text(
        "character:\n  name: Other\n  prompt_file: prompt.md\n", encoding="utf-8"
    )
    (root / "other" / "prompt.md").write_text("# OTHER\nEres Other.\n", encoding="utf-8")
    return root
