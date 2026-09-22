.PHONY: install run test test-all lint smoke

install:
	uv sync

run:
	uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

test:
	uv run pytest tests/unit -q

test-all:
	WINDLAYA_RUN_MODEL_TESTS=true uv run pytest -q

lint:
	uv run ruff check .

smoke:
	uv run python scripts/smoke_test.py
