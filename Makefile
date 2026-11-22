BACKEND := apps/backend
DESKTOP := apps/desktop
PY := $(BACKEND)/.venv/bin
AVATAR_PY := tools/avatar/.venv/bin

.PHONY: setup setup-backend setup-desktop setup-avatar-tool avatar backend backend-dev desktop test lint build check

setup: setup-backend setup-desktop

setup-backend:
	cd $(BACKEND) && python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"

setup-desktop:
	cd $(DESKTOP) && npm install

# Optional: only needed to (re)generate sprite avatar assets.
setup-avatar-tool:
	python3.12 -m venv tools/avatar/.venv && $(AVATAR_PY)/pip install -r tools/avatar/requirements.txt

# Regenerates sprite assets from characters/*/avatar.yaml (first run downloads a model).
# One character only: make avatar CHARACTER=mimi
CHARACTER ?= *
avatar:
	$(AVATAR_PY)/python tools/avatar/prepare_sprites.py characters/$(CHARACTER)/avatar.yaml

backend:
	cd $(BACKEND) && .venv/bin/python -m app.main

backend-dev:
	cd $(BACKEND) && .venv/bin/uvicorn app.main:create_app --factory --reload --no-access-log --host 127.0.0.1 --port 8000

desktop:
	cd $(DESKTOP) && npm run dev

test:
	cd $(BACKEND) && .venv/bin/pytest
	cd $(DESKTOP) && npm test

lint:
	cd $(BACKEND) && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app tests
	$(PY)/ruff check --config $(BACKEND)/pyproject.toml tools && $(PY)/ruff format --check --config $(BACKEND)/pyproject.toml tools
	cd $(DESKTOP) && npm run lint && npm run typecheck

build:
	cd $(DESKTOP) && npm run build

check: lint test build
