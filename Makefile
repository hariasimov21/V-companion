BACKEND := apps/backend
DESKTOP := apps/desktop
PY := $(BACKEND)/.venv/bin

.PHONY: setup setup-backend setup-desktop backend backend-dev desktop test lint build check

setup: setup-backend setup-desktop

setup-backend:
	cd $(BACKEND) && python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"

setup-desktop:
	cd $(DESKTOP) && npm install

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
	cd $(DESKTOP) && npm run lint && npm run typecheck

build:
	cd $(DESKTOP) && npm run build

check: lint test build
