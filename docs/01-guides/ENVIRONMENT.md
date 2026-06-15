# 环境变量配置指南

> 详细说明 litchi-head 的双 Key 体系 + 模型快慢分离策略。日常开发不需要读此文档 — 只在配置变更时参考。

---

## 模型策略（快慢分离）

| 环境变量 | 日常值 | 复杂任务值 | 说明 |
|------|------|------|------|
| `ANTHROPIC_MODEL` | `deepseek-chat` | `deepseek-v4-pro` | 默认用快速模型 |
| `ANTHROPIC_BASE_URL` | `https://api.deepseek.com/anthropic` | 不变 | DeepSeek 端点 |
| `CLAUDE_CODE_EFFORT_LEVEL` | **删除/不设** | 可选 `max` | 日常不需要 |

> **修改后必须完全退出并重启 Claude Code**。

## 两套 Key，不可混用

### Claude Code 主会话（DeepSeek 开发）

```bash
# Windows 用户环境变量（修改后必须完全退出并重启 Claude Code）
DEEPSEEK_API_KEY=sk-你的DeepSeek密钥
ANTHROPIC_AUTH_TOKEN=sk-你的DeepSeek密钥
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
ANTHROPIC_MODEL=deepseek-chat
# CLAUDE_CODE_EFFORT_LEVEL — 不设，日常无需推理
```

> 若把 `ANTHROPIC_BASE_URL` 设为 `lingsuan.top`，主会话会把 DeepSeek Key 发到灵算 → **401 API Key 无效**。

### Python 应用代码（`.env`）

`src/utils/llm.py` 的 `provider="anthropic"` 分支走灵算，与 Claude Code 主会话隔离：

```bash
DEEPSEEK_API_KEY=sk-你的DeepSeek密钥
LLM_PROVIDER=deepseek
ANTHROPIC_AUTH_TOKEN=sk-你的灵算密钥
ANTHROPIC_BASE_URL=https://lingsuan.top
```

### 子 Agent（Claude Code 内置）

Claude Code 的 `ANTHROPIC_BASE_URL` 是**会话级**配置，同一进程内主会话与子 Agent 共用同一端点。当前版本**无法**在同一 Claude Code 会话中做到「主会话 DeepSeek + 子 Agent 灵算 Claude」。子 Agent 会跟随主会话走 DeepSeek；灵算 Key 仅用于 `.env` 中 Python 代码显式指定 `provider="anthropic"` 时。

---

## 故障排查

| 症状 | 根因 | 修复 |
|------|------|------|
| 主会话 401 | `ANTHROPIC_BASE_URL` 指向灵算 | 改回 `api.deepseek.com/anthropic` |
| 子 Agent 400（reasoning_effort） | DeepSeek 对子 Agent 不兼容该参数 | 见 memory `agent-reasoning-effort-deepseek` |
| Python 代码灵算不通 | `.env` 中 `ANTHROPIC_BASE_URL` 或 Key 错误 | 检查 `.env` 中灵算配置 |
