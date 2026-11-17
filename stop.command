#!/bin/bash
# 荔枝头 · 停止服务（macOS / Linux）
# 用法：双击本文件。会结束占用 8000（后端）和 3000（前端）端口的进程，
# 不管它们是从哪个目录启动的。之后再双击 start.command 即可启动当前版本。

say() { printf '%s\n' "$*"; }
say "🍒 荔枝头 · 停止服务"

stopped=0
for port in 3000 8000; do
  pids="$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u)"
  if [ -z "$pids" ]; then
    say "端口 $port：没有正在运行的服务。"
    continue
  fi
  for pid in $pids; do
    say "端口 $port：结束进程 $pid（$(ps -o comm= -p "$pid" 2>/dev/null | sed 's|.*/||')）"
    kill -TERM "$pid" 2>/dev/null && stopped=1
  done
done

if [ "$stopped" -eq 1 ]; then
  sleep 2
  for port in 3000 8000; do
    for pid in $(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u); do
      say "端口 $port：进程 $pid 未退出，强制结束。"
      kill -KILL "$pid" 2>/dev/null
    done
  done
  sleep 1
fi

for port in 3000 8000; do
  if lsof -nP -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    say "⚠️  端口 $port 仍被占用：可能有别的程序在自动重启它。"
  fi
done
say "完成。"
