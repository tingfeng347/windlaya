.PHONY: install models run test test-all lint smoke

install:
	uv sync

models:
	uv run windlaya-models download

run:
	uv run windlaya

test:
	uv run pytest tests/unit -q

test-all:
	WINDLAYA_RUN_MODEL_TESTS=true uv run pytest -q

lint:
	uv run ruff check .

smoke:
	uv run python scripts/smoke_test.py
