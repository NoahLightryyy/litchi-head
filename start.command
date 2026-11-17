#!/bin/bash
# 荔枝头 · 一键启动（macOS / Linux）
# 用法：在 Finder 里双击本文件；或在终端执行 ./start.command
# 做的事：检查环境 → 首次自动安装依赖 → 启动后端(8000)和前端(3000) → 打开浏览器。
# 关闭本窗口或按 Ctrl+C 即停止全部服务。

set -u
cd "$(dirname "$0")" || exit 1
ROOT="$(pwd)"
VENV_DIR="${LITCHI_VENV:-$ROOT/.venv}"
BACKEND_PORT=8000
FRONTEND_PORT=3000
BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}/api/health"
FRONTEND_URL="http://localhost:${FRONTEND_PORT}"
LOG_DIR="$ROOT/logs"
BACKEND_LOG="$LOG_DIR/launcher-backend.log"
FRONTEND_LOG="$LOG_DIR/launcher-frontend.log"
BACKEND_PID=""
FRONTEND_PID=""

say()  { printf '%s\n' "$*"; }
step() { printf '\n▶ %s\n' "$*"; }
fail() {
  printf '\n❌ %s\n' "$1"
  shift
  for line in "$@"; do printf '   %s\n' "$line"; done
  printf '\n按回车键关闭窗口…'
  read -r _ || true
  exit 1
}

cleanup() {
  trap - EXIT INT TERM
  if [ -n "$FRONTEND_PID" ] || [ -n "$BACKEND_PID" ]; then
    say ""
    say "正在停止服务…"
  fi
  for pid in $FRONTEND_PID $BACKEND_PID; do
    pkill -TERM -P "$pid" 2>/dev/null
    kill -TERM "$pid" 2>/dev/null
  done
  wait 2>/dev/null
}
trap cleanup EXIT
trap 'exit 130' INT TERM

http_ok() { curl -fsS -o /dev/null --max-time 3 "$1" 2>/dev/null; }
port_busy() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

wait_for() {  # wait_for <url> <pid> <seconds>
  local url="$1" pid="$2" left="$3"
  while [ "$left" -gt 0 ]; do
    http_ok "$url" && return 0
    kill -0 "$pid" 2>/dev/null || return 2
    sleep 1
    left=$((left - 1))
  done
  return 1
}

say "🍒 荔枝头 · 一键启动"
mkdir -p "$LOG_DIR"

# ── 0. 已经在运行？直接打开浏览器 ──────────────────────────────
if http_ok "$BACKEND_URL" && http_ok "$FRONTEND_URL"; then
  say "服务已经在运行，直接打开浏览器。"
  command -v open >/dev/null 2>&1 && open "$FRONTEND_URL"
  exit 0
fi
for port in $BACKEND_PORT $FRONTEND_PORT; do
  if port_busy "$port"; then
    fail "端口 $port 已被其他程序占用。" \
         "如果是上一次没关干净的荔枝头：关掉之前的启动窗口后重试。" \
         "查看占用者：lsof -nP -iTCP:$port -sTCP:LISTEN"
  fi
done

# ── 1. Python ──────────────────────────────────────────────────
step "检查 Python（需要 3.12 或更高）"
PY=""
if [ -x "$VENV_DIR/bin/python" ] && "$VENV_DIR/bin/python" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
  PY="$VENV_DIR/bin/python"
  say "使用已有虚拟环境：$("$PY" --version 2>&1)"
else
  for candidate in python3.13 python3.12 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
      say "创建虚拟环境（首次运行）：$("$candidate" --version 2>&1)"
      "$candidate" -m venv "$VENV_DIR" || fail "创建虚拟环境失败。" "目录：$VENV_DIR"
      PY="$VENV_DIR/bin/python"
      break
    fi
  done
fi
[ -n "$PY" ] || fail "没有找到 Python 3.12+。" "请从 https://www.python.org/downloads/ 安装后重试。"

# ── 2. Python 依赖（按 constraints.txt 锁定版本） ───────────────
DEPS_STAMP="$VENV_DIR/.litchi-deps"
DEPS_WANT="$(cat pyproject.toml constraints.txt | cksum)"
if [ "$(cat "$DEPS_STAMP" 2>/dev/null)" != "$DEPS_WANT" ]; then
  if [ ! -f "$DEPS_STAMP" ] && "$PY" -c 'import fastapi, uvicorn, langgraph, akshare, src' 2>/dev/null; then
    say "Python 依赖已就绪。"
  else
    step "安装 Python 依赖（首次或依赖有更新，需要几分钟）"
    "$PY" -m pip install --disable-pip-version-check -q -e ".[dev]" -c constraints.txt \
      || fail "Python 依赖安装失败。" "请检查网络后重试；完整输出见上方。"
  fi
  printf '%s' "$DEPS_WANT" > "$DEPS_STAMP"
else
  say "Python 依赖已就绪。"
fi

# ── 3. 配置与密钥提示（不阻断：行情浏览不需要密钥） ─────────────
if [ ! -f .env ]; then
  cp .env.example .env
  say "已从 .env.example 生成 .env。"
fi
if ! grep -Eq '^DEEPSEEK_API_KEY=.+' .env && \
   ! "$PY" -c 'import keyring,sys; sys.exit(0 if keyring.get_password("litchi-head","DEEPSEEK_API_KEY") else 1)' 2>/dev/null; then
  say "⚠️  未检测到 DeepSeek 密钥：行情与图表可用，AI 研究会提示不可用。"
  say "   设置方法：$PY scripts/store-api-keys.py --set DEEPSEEK_API_KEY"
fi

# ── 4. Node / pnpm ─────────────────────────────────────────────
step "检查 Node.js（需要 20 或更高，建议 24）"
command -v node >/dev/null 2>&1 || fail "没有找到 Node.js。" "请从 https://nodejs.org/ 安装 LTS 版本后重试。"
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
[ "$NODE_MAJOR" -ge 20 ] || fail "Node.js 版本过低（当前 $(node --version)）。" "请升级到 20 或更高。"
say "Node.js $(node --version)"
if command -v pnpm >/dev/null 2>&1; then
  pnpm_run() { pnpm "$@"; }
elif command -v corepack >/dev/null 2>&1; then
  pnpm_run() { corepack pnpm@10.33.0 "$@"; }
else
  fail "没有找到 pnpm。" "请执行：npm install -g pnpm@10.33.0 后重试。"
fi

if [ ! -d frontend/node_modules ]; then
  step "安装前端依赖（首次运行，需要几分钟）"
  pnpm_run --dir frontend install --frozen-lockfile || fail "前端依赖安装失败。" "请检查网络后重试。"
fi

# ── 5. 前端构建（源码有变化才重建） ────────────────────────────
BUILD_ID="frontend/.next/BUILD_ID"
NEED_BUILD=0
if [ ! -f "$BUILD_ID" ]; then
  NEED_BUILD=1
elif [ -n "$(find frontend/app frontend/components frontend/lib frontend/package.json frontend/next.config.ts frontend/pnpm-lock.yaml -newer "$BUILD_ID" -print 2>/dev/null | head -n 1)" ]; then
  NEED_BUILD=1
fi
if [ "$NEED_BUILD" -eq 1 ]; then
  step "构建前端（首次或界面有更新，约 1 分钟）"
  pnpm_run --dir frontend build > "$FRONTEND_LOG" 2>&1 \
    || { tail -n 30 "$FRONTEND_LOG"; fail "前端构建失败。" "完整日志：$FRONTEND_LOG"; }
fi

# ── 6. 启动后端 ────────────────────────────────────────────────
step "启动后端（端口 ${BACKEND_PORT}）"
PYTHONUTF8=1 "$PY" -m uvicorn backend.main:app --host 127.0.0.1 --port "$BACKEND_PORT" > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
wait_for "$BACKEND_URL" "$BACKEND_PID" 90
case $? in
  0) say "后端就绪。" ;;
  2) tail -n 30 "$BACKEND_LOG"; BACKEND_PID=""; fail "后端启动后立即退出。" "完整日志：$BACKEND_LOG" ;;
  *) tail -n 30 "$BACKEND_LOG"; fail "后端 90 秒内没有就绪。" "完整日志：$BACKEND_LOG" ;;
esac

# ── 7. 启动前端 ────────────────────────────────────────────────
step "启动前端（端口 ${FRONTEND_PORT}）"
pnpm_run --dir frontend exec next start --port "$FRONTEND_PORT" >> "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
wait_for "$FRONTEND_URL" "$FRONTEND_PID" 60
case $? in
  0) say "前端就绪。" ;;
  2) tail -n 30 "$FRONTEND_LOG"; FRONTEND_PID=""; fail "前端启动后立即退出。" "完整日志：$FRONTEND_LOG" ;;
  *) tail -n 30 "$FRONTEND_LOG"; fail "前端 60 秒内没有就绪。" "完整日志：$FRONTEND_LOG" ;;
esac

# ── 8. 打开浏览器并守护 ────────────────────────────────────────
command -v open >/dev/null 2>&1 && open "$FRONTEND_URL"
say ""
say "✅ 荔枝头已启动：$FRONTEND_URL"
say "   日志：$BACKEND_LOG"
say "         $FRONTEND_LOG"
say "   关闭本窗口或按 Ctrl+C 即停止。"

while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 2
done
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  tail -n 30 "$BACKEND_LOG"
  fail "后端意外退出。" "完整日志：$BACKEND_LOG"
fi
tail -n 30 "$FRONTEND_LOG"
fail "前端意外退出。" "完整日志：$FRONTEND_LOG"
