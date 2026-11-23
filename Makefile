BACKEND := apps/backend
DESKTOP := apps/desktop
TTS := apps/tts
PY := $(BACKEND)/.venv/bin
AVATAR_PY := tools/avatar/.venv/bin

.PHONY: dev web setup setup-backend setup-desktop setup-tts setup-avatar-tool avatar voice tts backend backend-dev desktop test lint build check

setup: setup-backend setup-desktop

setup-backend:
	cd $(BACKEND) && python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"

setup-desktop:
	cd $(DESKTOP) && npm install

# Optional: the character's spoken voice (NVIDIA GPU with CUDA 12.8+ drivers; ~250 MB).
QWENTTS_WHEELS := https://huggingface.co/datasets/andito/qwentts-cpp-python-wheels/tree/main/whl/cu128
setup-tts:
	rm -rf $(TTS)/.venv
	cd $(TTS) && python3.12 -m venv .venv && .venv/bin/pip install -f $(QWENTTS_WHEELS) -e ".[dev]"

# Optional: only needed to (re)generate sprite avatar assets.
setup-avatar-tool:
	python3.12 -m venv tools/avatar/.venv && $(AVATAR_PY)/pip install -r tools/avatar/requirements.txt

# Regenerates sprite assets from characters/*/avatar.yaml (first run downloads a model).
# One character only: make avatar CHARACTER=mimi
CHARACTER ?= *
avatar:
	$(AVATAR_PY)/python tools/avatar/prepare_sprites.py characters/$(CHARACTER)/avatar.yaml

# Designs a character's voice from characters/<id>/voice.yaml (3 candidates).
# Pick another candidate with: make voice CHARACTER=mimi PICK=2
PICK ?=
voice:
	cd $(TTS) && .venv/bin/python -m tts_service.design $(CHARACTER) $(if $(PICK),--pick $(PICK))

# Local TTS service on 127.0.0.1:8010 (the backend works without it, text-only).
tts:
	cd $(TTS) && .venv/bin/python -m tts_service.server

# Everything in one terminal (voice if installed, backend, app). Ctrl+C stops all.
# Without voice: make dev NO_VOICE=1 · Browser instead of the window: make dev WEB=1
dev:
	NO_VOICE=$(NO_VOICE) WEB=$(WEB) ./scripts/dev.sh

# The UI as a web page on http://127.0.0.1:5173 (no Electron window).
web:
	cd $(DESKTOP) && npm run web

backend:
	cd $(BACKEND) && .venv/bin/python -m app.main

backend-dev:
	cd $(BACKEND) && .venv/bin/uvicorn app.main:create_app --factory --reload --no-access-log --host 127.0.0.1 --port 8000

desktop:
	cd $(DESKTOP) && npm run dev

test:
	cd $(BACKEND) && .venv/bin/pytest
	if [ -d $(TTS)/.venv ]; then cd $(TTS) && .venv/bin/pytest; fi
	cd $(DESKTOP) && npm test

lint:
	cd $(BACKEND) && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app tests
	$(PY)/ruff check --config $(BACKEND)/pyproject.toml tools && $(PY)/ruff format --check --config $(BACKEND)/pyproject.toml tools
	$(PY)/ruff check --config $(TTS)/pyproject.toml $(TTS) && $(PY)/ruff format --check --config $(TTS)/pyproject.toml $(TTS)
	cd $(DESKTOP) && npm run lint && npm run typecheck

build:
	cd $(DESKTOP) && npm run build

check: lint test build
