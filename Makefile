.PHONY: help install dev lint format type test test-unit test-integration test-all eval clean start stop logs

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'

install: ## Install package + dev dependencies
	pip install -e ".[dev]"
	pre-commit install

lint: ## Run ruff linter
	ruff check src/ tests/

format: ## Format code with ruff
	ruff format src/ tests/

type: ## Type-check with mypy
	mypy src/orchestrix --ignore-missing-imports

test: ## Run unit tests
	pytest tests/unit -v

test-unit: ## Run unit tests only
	pytest tests/unit -v

test-integration: ## Run integration tests (requires DB)
	docker compose -f docker/docker-compose.yml up postgres -d
	sleep 3
	pytest tests/integration -v

test-all: ## Run all tests
	pytest tests/ -v --cov=src/orchestrix --cov-report=term-missing

eval: ## Run evaluation suite
	python -m orchestrix.evaluation.cli run \
		--benchmark data/benchmarks/safe_unsafe_actions.json \
		--output evaluation/reports/dev.json \
		--mode dev

start: ## Start full local stack
	./scripts/start.sh

stop: ## Stop Docker stack
	docker compose -f docker/docker-compose.yml down

logs: ## Tail logs from API container
	docker compose -f docker/docker-compose.yml logs -f api

clean: ## Clean Python + DVC caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .ruff_cache htmlcov .coverage
