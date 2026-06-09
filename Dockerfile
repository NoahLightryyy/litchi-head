# ── litchi-head 开发容器 ─────────────────────────────────────────────
# 用途：消除设备更换导致的环境不一致问题
# 用法：docker compose run --rm dev <command>
#       make docker-test

FROM python:3.12-slim

WORKDIR /app

# ── 系统依赖（akshare / pandas 所需底层库） ──────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# ── 安装项目依赖（利用 Docker 层缓存提速） ─────────────────────
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[dev,frontend]"

# ── 默认命令 ─────────────────────────────────────────────────────
CMD ["python", "-m", "pytest", "-v", "--tb=short"]
