.PHONY: help install dev browsers test lint typecheck run once docker-build docker-run clean

help:
	@echo "Targets:"
	@echo "  install      Install runtime deps + the package"
	@echo "  dev          Install dev deps (tests, linters)"
	@echo "  browsers     Install the Playwright Chromium browser"
	@echo "  test         Run the test suite"
	@echo "  lint         Run ruff"
	@echo "  typecheck    Run mypy"
	@echo "  once         Run a single check, print to console"
	@echo "  run          Start the polling watcher"
	@echo "  docker-build Build the Docker image"
	@echo "  docker-run   Run a one-off check in Docker"

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

browsers:
	python -m playwright install chromium

test:
	pytest

lint:
	ruff check src tests

typecheck:
	mypy src

once:
	flight-tracker --once --console

run:
	flight-tracker

docker-build:
	docker build -t flight-tracker:latest .

docker-run:
	docker run --rm --env-file .env flight-tracker:latest --once --console

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info screenshots
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
