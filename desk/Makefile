PY ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
PORT ?= 8000

.PHONY: help venv install ui-install ui-build dev api ui test lint fmt clean docker

help:
	@echo "make install    - create venv, install package + dev deps, install UI deps"
	@echo "make dev        - run API (:$(PORT)) and Vite dev server (:5173) together"
	@echo "make api        - run the FastAPI app only (serves built UI if present)"
	@echo "make ui-build   - build the UI into src/optionsdesk/static"
	@echo "make test       - run the Python test suite"
	@echo "make lint       - ruff + tsc"
	@echo "make docker     - docker compose up --build"

$(BIN)/python:
	$(PY) -m venv $(VENV) || ($(PY) -m venv --without-pip $(VENV) && curl -sS https://bootstrap.pypa.io/get-pip.py | $(BIN)/python)

venv: $(BIN)/python

install: venv
	$(BIN)/pip install -q -e ".[dev]"
	cd ui && npm install --no-audit --no-fund

ui-install:
	cd ui && npm install --no-audit --no-fund

ui-build:
	cd ui && npm run build

api:
	$(BIN)/uvicorn --factory optionsdesk.app:create_app --host 0.0.0.0 --port $(PORT) --reload

ui:
	cd ui && npm run dev

dev:
	@trap 'kill 0' EXIT; \
	$(MAKE) api & \
	$(MAKE) ui & \
	wait

test:
	$(BIN)/pytest

lint:
	$(BIN)/ruff check src tests
	$(BIN)/ruff format --check src tests
	cd ui && npm run typecheck

fmt:
	$(BIN)/ruff format src tests
	$(BIN)/ruff check --fix src tests

docker:
	docker compose up --build

clean:
	rm -rf $(VENV) ui/node_modules ui/dist-lib src/optionsdesk/static data/*.sqlite3* .pytest_cache .ruff_cache
