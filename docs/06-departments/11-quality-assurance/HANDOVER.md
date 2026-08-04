---
department: 质量保障部
codebase: .github/workflows/ + tests/ + docs/01-guides/ci/ + docs/01-guides/workflow/
last_updated: 2026-08-03 (TD-072 全量闸门通过)
---

# 🔄 质量保障部工作交接

## 当前状态

### CI 系统状态

| 指标 | 值 |
|:-----|:----|
| GitHub Actions 最新状态 | ✅ Run #72 全绿（frontend + Python 3.12/3.13） |
| 最近一次绿色 | Run #72 — `test: isolate CI from network and clock drift`（2026-07-31） |
| Python 3.12/3.13 | Run #71 均因辩论路由测试泄漏真实 AKShare 网络而失败；已修复 |
| 本地全量闸门 | ✅ 4/4；1600 passed、4 skipped、19 slow deselected |
| Ruff | ✅ 通过 |

### 当前 CI 问题

| ID | 标题 | 严重度 | 状态 |
|:--|:-----|:------:|:----:|
| CI-001 | 历史 CI 连红治理 | 🔴 P0 | ✅ 已恢复并可读取远端日志 |
| CI-002 | Python 3.13 Pyright 超时 | 🟡 P2 | ✅ 当前运行未复现 |
| CI-003 | 测试泄漏真实行情网络与系统日期 | 🔴 P0 | ✅ `a352fb0` 已修复，Run #72 全绿 |

### 根因分析进展

**Run #71 根因与处置**（2026-07-31）：
- Python 3.12/3.13 的 Ruff、Pyright 均通过，前端任务通过；
- 三个 `tests/test_backend/test_debate.py` 场景在 POST `/api/debate/run` 时未继承
  类级股票名称 mock，因而访问真实 AKShare/上交所网络并失败；
- 将 `resolve_stock_name` mock 提升为模块级 autouse fixture，同时保留成功解析与
  空名称 fail-closed 的内层显式覆盖；
- 跨日后另发现北交所生命周期样本将响应截止日固定为 2026-07-30、却使用系统当天
  作为查询截止日；测试已把消费方时钟固定到样本日期；
- 两项修复只隔离测试的网络与时钟，不改变生产数据规则。专项 23 passed，完整闸门
  1592 passed、4 skipped、19 deselected。

---

## 文档索引

| 文档 | 位置 |
|:-----|:------|
| 👤 ROLE | `docs/06-departments/11-quality-assurance/ROLE.md` |
| 📐 STANDARDS | `docs/06-departments/11-quality-assurance/STANDARDS.md` |
| 💳 DEBT | `docs/06-departments/11-quality-assurance/DEBT.md` |
| 🟢 CI 门禁标准 | `docs/01-guides/ci/STANDARDS.md` |
| 🔧 CI 处理工作流 | `docs/01-guides/ci/WORKFLOW.md` |
| 📋 本地检查清单 | `docs/01-guides/ci/CHECKS.md` |
| 🏥 根因知识库 | `docs/01-guides/ci/TROUBLESHOOTING.md` |
| 📘 维护手册 | `docs/01-guides/ci/HANDBOOK.md` |
| 📊 CI 问题追踪 | `docs/01-guides/ci/ISSUES.md` |

---

## 下一步优先级

### 现有 CI 问题

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:-----|
| 1 🟢 | **测试隔离纪律** — 单元/路由测试不得访问真实行情网络；时间相关样本必须冻结时钟 | 持续执行 |
| 2 🟢 | **定期审视** — 每周检查 CI 状态趋势 | 无 |
| 🔥 | **TD-069/KR-6 K 线全链路验收** — 来源独立性、RAW、复权、点时、四层状态、零 LLM、交易价格、API/UI 和故障注入 | KR-3A 51 项契约通过；下一步 KR-3B 运行时组装 |

### 决策 baseline / 影子验证（TD-074）

完整口径见 [跨部门唯一协议](../../02-requirements/DECISION_BASELINE_AND_SHADOW_VALIDATION.md)。
质量保障部负责验证生产 E2E 不绕过证据/风控门、影子报告可从冻结数据重复生成、失败样本
不会被删去，并对数据源故障、模型超时、进程重启和前端离线做黑盒故障注入。

### 设计哲学回归验证（DP 系列）

> 基于 2026-06-22 设计哲学会议。以下任务实施后质量保障部负责回归验证。

| DP | 回归验证内容 | 预估 |
|:--:|:-----------|:----:|
| **DP-001** | 模型瘦身后全量测试 946 无回归，pyright 零错误 | ~15min |
| **DP-002** | D1 同侪审阅改 prompt → 测试验证输出结构变化但无回归 | ~15min |
| **DP-004** | TrustTracker 新增旋钮 → 现有 54 个信任度测试不破坏 | ~10min |
| **DP-005** | 灵感官 Agent 注册 → 不破坏现有辩论链路 | ~10min |

### 用户经验反馈闭环回归验证（UI 系列）

> 完整方案见 [USER_FEEDBACK_LOOP.md](../../02-requirements/USER_FEEDBACK_LOOP.md)。
> 质量保障部负责 UI 系列实施后的回归验证。

| UI | 回归验证内容 | 预估 |
|:--:|:-----------|:----:|
| **UI-1a** | RC-001 回调引擎上线 → 全量测试不破坏；`tests/test_callback/` 新测试 80%+ 覆盖 | ~20min |
| **UI-1b** | RC-003 用户操作 API → 现有 debate/backend 测试不回归 | ~15min |
| **UI-3** | RetroBoard 前后端 → 现有前端 pnpm build 零错误 | ~10min |
| **UI-4a** | 镜子 Agent → 现有大师 Agent 注册和辩论链路不受影响 | ~15min |

---

> **最后更新**: 2026-07-31 | Run #71 测试隔离修复，Run #72 全绿
