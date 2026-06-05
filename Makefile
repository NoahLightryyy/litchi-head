.PHONY: help install lint type test check clean

help:
	@echo "====================  litchi-head  ===================="
	@echo "Available targets:"
	@echo "  make install  - Install project with dev dependencies"
	@echo "  make lint     - Run Ruff code style/lint check"
	@echo "  make type     - Run Pyright type checking on src/"
	@echo "  make test     - Run pytest with verbose output"
	@echo "  make check    - Run ALL checks (lint + type + test)"
	@echo "  make clean    - Remove __pycache__ and .pyc files"
	@echo "========================================================"

install:
	pip install --upgrade pip
	pip install -e ".[dev]"

lint:
	ruff check .

type:
	pyright src/

test:
	pytest -v --tb=short

check: lint type test

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
