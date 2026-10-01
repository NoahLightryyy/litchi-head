> 2026-10-01 运行修复：用户已批准产品分析临时使用 `deepseek-v4-pro` 非思考模式；Flash 实网仅返回保活消息。当前产品默认以 `src/utils/llm.py::DEFAULT_MODEL` 为准。下文快速模型策略为长期目标，不改变当前开发助手模型。

# 环境变量配置指南

> 说明 litchi-head 的本地工具链、凭据隔离和模型快慢分离策略。日常开发不需要读此文档 — 只在配置变更时参考。

## 本地工具链基线

| 工具 | 项目要求 | 2026-08-25 Windows 验证版本 |
|------|----------|----------------------------|
| Git | 必需 | 2.55.0 |
| Python | 3.12+，使用 `litchi` Conda 环境 | 3.12.14 |
| Node.js | Next.js 16 支持版本，优先 LTS | 24.19.0 LTS |
| pnpm | 使用 `frontend/pnpm-lock.yaml` | 10.33.0 |
| fnm | Windows 用户级 Node 版本管理（推荐） | 1.39.0，默认 Node 24.19.0 |
| Docker / Make | 可选；Windows 本地开发不要求 | 未安装也可通过闸门 |

Python 依赖从根目录安装：`pip install -e ".[dev]"`。前端依赖在 `frontend/`
执行 `pnpm install --frozen-lockfile`。Windows 中文控制台运行 Python 工具前建议设置
`$env:PYTHONUTF8 = "1"`；项目的 `start_dev.ps1` 已包含该设置。

---

## 模型策略（快慢分离）

| 环境变量 | 日常值 | 复杂任务值 | 说明 |
|------|------|------|------|
| `ANTHROPIC_MODEL` | `deepseek-flash` | `deepseek-v4-pro` | 默认用快速模型 |
| `ANTHROPIC_BASE_URL` | `https://api.deepseek.com/anthropic` | 不变 | DeepSeek 端点 |
| `CLAUDE_CODE_EFFORT_LEVEL` | **删除/不设** | 可选 `max` | 日常不需要 |

> **修改后必须完全退出并重启 Claude Code**。

## 两类运行环境，不可混用

### Claude Code 主会话（DeepSeek 开发）

```bash
# Windows 用户环境变量（修改后必须完全退出并重启 Claude Code）
DEEPSEEK_API_KEY=sk-你的DeepSeek密钥
ANTHROPIC_AUTH_TOKEN=sk-你的DeepSeek密钥
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
ANTHROPIC_MODEL=deepseek-flash
# CLAUDE_CODE_EFFORT_LEVEL — 不设，日常无需推理
```

> 若把 `ANTHROPIC_BASE_URL` 设为 `lingsuan.top`，主会话会把 DeepSeek Key 发到灵算 → **401 API Key 无效**。

### Python 应用代码（Windows 凭据管理器 + `.env`）

Python 应用当前只使用 DeepSeek。真实 Key 写入 Windows Credential Manager，`.env`
只保留非敏感运行配置：

```bash
# 在已激活的 litchi 环境中交互录入，不会回显或写入仓库文件
python scripts/store-api-keys.py --set DEEPSEEK_API_KEY

# .env
DEEPSEEK_API_KEY=
LLM_PROVIDER=deepseek
DEBUG=true
LOG_LEVEL=DEBUG
```

可用 `python scripts/store-api-keys.py --status` 检查是否已配置；该命令只显示状态，
不会输出密钥明文。

### 子 Agent（Claude Code 内置）

Claude Code 的 `ANTHROPIC_BASE_URL` 是**会话级**配置，同一进程内主会话与子 Agent
共用同一端点，子 Agent 会跟随主会话。Python 应用的 DeepSeek 凭据与开发工具主会话
配置相互独立，禁止把开发工具的端点或 Token 复制进项目 `.env`。

---

## 故障排查

## K 线审计目录

`RawDailyKlineEvidenceRuntime` 默认把不可变审计快照写入
`<DATA_DIR>/evidence/kline-audit` 的绝对路径。需要迁移到独立磁盘时可配置：

```bash
LITCHI_KLINE_AUDIT_ROOT=E:\litchi-head\data\evidence\kline-audit
```

该变量必须是绝对路径；相对路径会在启动时显式拒绝，避免因工作目录变化把实盘
证据写到不同位置。目录内的 SQLite 清单和内容寻址 Parquet 必须作为同一整体备份。

| 症状 | 根因 | 修复 |
|------|------|------|
| 主会话 401 | `ANTHROPIC_BASE_URL` 指向灵算 | 改回 `api.deepseek.com/anthropic` |
| 子 Agent 400（reasoning_effort） | DeepSeek 对子 Agent 不兼容该参数 | 见 memory `agent-reasoning-effort-deepseek` |
| Python 代码灵算不通 | `.env` 中 `ANTHROPIC_BASE_URL` 或 Key 错误 | 检查 `.env` 中灵算配置 |
