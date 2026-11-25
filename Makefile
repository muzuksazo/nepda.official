.PHONY: help setup-python setup-node test-all dev-worker dev-planner check-health

help:
	@echo "Dual-SDK Monorepo Targets (nepda.oficial)"
	@echo "  make setup-python   Install Python google-genai worker venv via uv"
	@echo "  make setup-node     Install TypeScript Vercel ai-sdk planner packages"
	@echo "  make test-all       Run scripts (13), production worker (5+), and ai-sdk planner tests"
	@echo "  make dev-worker     Start Python google-genai FastAPI worker on :8080"
	@echo "  make dev-planner    Start TypeScript Vercel ai-sdk planner API on :8787"
	@echo "  make check-health   Probe both local planner (:8787) and worker (:8080)"

setup-python:
	uv venv production/.venv --python 3.11
	uv pip install --python production/.venv/bin/python -r production/requirements.txt

setup-node:
	cd planner-ai-sdk && npm install

test-all:
	python3 -m unittest discover -s skills/shortform-ad-remix-director/scripts -p "test_*.py" -v
	PYTHONPATH=production production/.venv/bin/python -m unittest discover -s production/tests -p "test_*.py" -v
	cd planner-ai-sdk && npm run typecheck && npm run build && npm test

dev-worker:
	PYTHONPATH=production production/.venv/bin/uvicorn app.server:app --host 127.0.0.1 --port 8080

dev-planner:
	cd planner-ai-sdk && npm run dev

check-health:
	curl -fsS http://127.0.0.1:8787/health && echo ""
	curl -fsS http://127.0.0.1:8080/health && echo ""
