.PHONY: help setup-python setup-node test-all test-python test-node dev-worker dev-planner build-prototype check-health

PYTHON_VERSION ?= 3.12
ifeq ($(OS),Windows_NT)
PYTHON = .venv/Scripts/python.exe
else
PYTHON = .venv/bin/python
endif

help:
	@echo "NAPDA apps / libraries / prototypes / PRD tests"
	@echo "  make setup-python   Install backend and media test dependencies"
	@echo "  make setup-node     Install planner workspace dependencies"
	@echo "  make test-all       Run Python/Node tests, typecheck and build"
	@echo "  make dev-worker     Start apps/backend on :8080"
	@echo "  make dev-planner    Start libraries/planner-api on :8787"
	@echo "  make build-prototype   Build the existing web prototype"
	@echo "  make check-health   Check planner and backend health"

setup-python:
	uv venv .venv --python $(PYTHON_VERSION)
	uv pip install --python $(PYTHON) -r apps/backend/requirements.txt

setup-node:
	npm ci

test-python:
	$(PYTHON) scripts/test-python.py

test-node:
	npm test
	npm run typecheck
	npm run build

test-all: test-python test-node

dev-worker:
	$(PYTHON) -m uvicorn app.server:app --app-dir apps/backend --host 127.0.0.1 --port 8080

dev-planner:
	node --env-file=libraries/planner-api/.env --import tsx libraries/planner-api/src/server.ts

build-prototype:
	node scripts/build-prototype.mjs

check-health:
	curl -fsS http://127.0.0.1:8787/health
	curl -fsS http://127.0.0.1:8080/health
