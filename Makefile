.PHONY: help install lint type test check clean docker-build docker-test docker-check docker-shell

help:
	@echo "====================  litchi-head  ===================="
	@echo "Available targets:"
	@echo "  make install  - Install project with dev dependencies"
	@echo "  make lint     - Run Ruff code style/lint check"
	@echo "  make type     - Run Pyright type checking on src/"
	@echo "  make test     - Run pytest with verbose output"
	@echo "  make check    - Run ALL checks (lint + type + test)"
	@echo "  make clean    - Remove __pycache__ and .pyc files"
	@echo ""
	@echo "Docker (环境一致性，推荐):"
	@echo "  make docker-build   - Build dev image"
	@echo "  make docker-test    - Run tests in container"
	@echo "  make docker-check   - Run full check in container"
	@echo "  make docker-shell   - Open bash in container"
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

# ── Docker 开发环境（保证跨设备环境一致） ────────────────────────────
# 前提：已安装 Docker Desktop

docker-build:
	docker compose build

docker-test:
	docker compose run --rm dev pytest -v --tb=short

docker-check:
	docker compose run --rm dev make check

docker-shell:
	docker compose run --rm dev bash
