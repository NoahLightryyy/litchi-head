# 20 三层测试策略 — pytest marker 实现快慢分离

## 一句话

> 用 `@pytest.mark.slow` 标记慢测试（>10s），pre-push hook 自动跳过，CI 负责全量，实现本地 <1min 反馈、CI 全量覆盖的渐进式验证。

---

## 为什么需要它？

### 问题场景

你的项目有 946 个测试。全量跑一次 **~12 分钟**。

然后你遇到了一个两难选择：

| 方案 | 效果 | 问题 |
|:-----|:------|:------|
| pre-push 跑全量 | 每次推送都过完整验证 | 等 12 分钟才能推送，开发者受不了，最后全用 `--no-verify` |
| pre-push 跑零测试 | 推送飞快 | 错了等 CI 报才知道，反馈周期从 12 分钟变 30 分钟+ |

两个极端都不对。

### 业界解法：渐进式验证

成熟项目（Guix、SymPy、Rust、WebKit）的共同模式是 **分层门禁**：

| 层级 | 耗时 | 跑什么 |
|:-----|:----:|:-------|
| 🔨 pre-push hook | <2min | 代码风格 + 类型检查 + **快测试子集** |
| ☁️ CI（PR） | 全量 | 所有测试（含慢测试） |
| 🌙 CI（nightly） | 极限 | 极慢测试（tooslow） |

关键做法：用 `@pytest.mark.slow` 标记 >10s 的测试，pre-push 自动跳过。

---

## 项目里的真实代码

### 1. 定义 marker

打开 `pyproject.toml`：

```toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow (>10s). Pre-push hook skips these with 'not slow'; CI runs full suite.",
]
```

### 2. 标记慢测试

在耗时 >10s 的测试类/方法上加 `@pytest.mark.slow`：

```python
@pytest.mark.slow          # ← 这 23 个测试被标记为 slow
class TestE2EFullPipeline:
    """端到端全链路 9 层测试（~300s 合计）"""
    ...

@pytest.mark.slow
class TestDebateOrchestratorRun:
    """辩论编排器全流程（~120s 合计）"""
    ...
```

标记范围可以是 **类级**（整个测试类都慢）或 **方法级**（单条测试慢）。

### 3. pre-push hook 跳过慢测试

打开 `scripts/pre-push`：

```bash
pytest -m "not slow" -x --tb=short   # 跳过 23 个慢测试，跑 919 个快测试
```

- `-m "not slow"` — 跳过标记为 slow 的测试
- `-x` — 遇到第一个失败就停（快速反馈）
- `--tb=short` — 精简报错输出

### Hook 中的 Git 环境隔离

Git 执行 hook 时会导出 `GIT_DIR`、`GIT_WORK_TREE`、`GIT_INDEX_FILE` 等变量。测试进程若
继承它们，那么测试中本应位于 `tmp_path` 的 `git init/commit` 仍可能写入真实仓库；只传
`cwd=tmp_path` 并不能覆盖环境变量。项目的 pre-push 因此先冻结当前 worktree 根，再执行：

```bash
HOOK_REPO_ROOT="$(git rev-parse --show-toplevel)"
GIT_LOCAL_ENV_VARS="$(git rev-parse --local-env-vars)"
unset $GIT_LOCAL_ENV_VARS
cd "$HOOK_REPO_ROOT"
```

hook 同时要求 worktree 完全干净，不自动 stash。linked worktree 共用 `refs/stash`，在长时间
测试期间按“最新 stash”恢复可能拿到其他 worktree 的条目；失败关闭比自动搬运用户文件更
可靠。

### 4. 验证效果

```bash
# 快测试子集（pre-push hook 自动）
pytest -m "not slow" -x --tb=short
# → 919 passed, 23 deselected, 26s ✅

# 慢测试（CI 跑）
pytest -m slow
# → 23 selected, ~600s

# 全量
pytest -v --tb=short
# → 946 tests, ~12min
```

---

## 分工原则

```
pre-push hook → ruff + pyright + 快测试子集（~35s）    ← 每次推送自动
GitHub CI     → ruff + pyright + 全量测试（含慢测试）   ← PR 合并前完整验证
手动 python scripts/check.py --full → ruff + pyright + 全量子集             ← 大重构前自选
```

**关键原则**：
- slow 标记的是**绝对耗时 >10s** 的测试，不是"偶尔会慢"的测试
- pre-push 不一定要零测试，关键是要 **<2min**
- CI 是全量门禁，pre-push 是快筛

### 前端为什么必须单独跑 ESLint

Next.js 16 已移除 `next lint`，而且 `next build` 也不再自动执行 lint。项目现在在
`frontend/eslint.config.mjs` 中显式启用 `core-web-vitals + typescript` flat config：

```javascript
export default defineConfig([
  ...nextVitals,
  ...nextTypeScript,
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
]);
```

`pnpm --dir frontend lint` 使用 `--max-warnings 0`，所以未使用变量、错误的内部 `<a>`
导航、Effect 中同步 setState 等问题都会阻断。`scripts/check.py` 在检测到 `frontend/`
变更时自动执行 lint 和类型检查，GitHub Actions 还会在构建前独立执行一次。

---

## 和单独用 `pytest.mark.integration` 有什么不同

| 对比 | `integration` | `slow` |
|:-----|:--------------|:-------|
| 目的 | 是否调用外部服务（API/DB） | 是否跑得慢（>10s） |
| 判定标准 | 逻辑维度 | 时间维度 |
| 是否互斥 | 否（可同时标记） | 否（可同时标记） |
| 示例 | `test_master_agent_real_llm` 标记了 `integration + slow` | 同上 |

**建议**：两个 marker 可以叠加使用。`slow` 控制 pre-push 跳过，`integration` 控制 CI 按需运行。

---

## 面试会怎么问

> **Q: 你的项目有多少测试？pre-push hook 跑多少？**
>
> A: 946 个测试中，23 个被 `@pytest.mark.slow` 标记（>10s 的全流程和真实 LLM 调用）。pre-push hook 跑 ruff + pyright + 919 个快测试，约 35 秒。23 个慢测试由 GitHub Actions CI 负责。这是一个**三层渐进式验证**策略，参考了 Guix 和 SymPy 等成熟项目的模式。

---

## 自己试试（5 分钟）

1. 运行 `pytest -m "not slow" -x --tb=short -q` 看看有多快
2. 运行 `pytest --collect-only -q -m slow` 看看哪些被标记为慢测试
3. 思考题：如果有一个新测试需要跑网络请求但很快（<3s），应该标记 `slow` 还是 `integration` 还是两者都要？

---

**上一篇：[Windows 开发环境调试指南 — Git Bash 5 大兼容坑](19-windows-git-bash-compat.md)**

---

> **更新**：2026-08-21 | 补充 Next.js 16 ESLint CLI 独立门禁
