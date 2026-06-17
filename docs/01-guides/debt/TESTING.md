# 🧪 测试债务

> 缺少 Mock 工具、测试覆盖率不足。

---

###### TD-004 缺少测试基座和 Mock 工具

| 属性 | 值 |
|------|-----|
| **分类** | `🧪 testing` `severity:moderate` `module:tests` `impact:可测试性` |
| **发现日期** | 2026-06-05 |
| **状态** | `🔧 修复中` |
| **本金估算** | ∼2h |

**描述**：
测试目录曾只有空 `__init__.py`，无实质测试，也无 Mock LLM 的工具。

**已实现**：
1. ✅ `tests/conftest.py` — 测试基座，含三个 Mock 工厂函数
2. ✅ `tests/test_sanity.py` — 24 个冒烟测试
3. ✅ `tests/test_agents_base.py` — 15 个 Agent 业务测试
4. ✅ `tests/test_core_protocol.py` — 20 个协议测试
5. ✅ `tests/test_utils_cost_tracker.py` — 15 个费用追踪测试
6. ✅ `tests/test_utils_llm.py` — 12 个 LLM 测试
7. ⬜ debate/memory/data 模块业务测试

---

###### TD-036 `backend/` 零测试覆盖（17 个 API 端点 + 核心计算逻辑）

| 属性 | 值 |
|------|-----|
| **分类** | `🧪 testing` `severity:critical` `module:backend` `impact:可靠性` |
| **发现日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼2d |
| **日利息** | 改 backend 代码全靠手动验证，改了坏了自己不知道 |
| **实盘影响** | 🔴 核心计算（MA/RSI/MACD）和数据接口无人验证，改错就是亏钱 |
| **触发场景** | 每次 backend 代码变更后 |
| **用户能发现吗** | ❌ 不能 — 测试没发现的问题，用户只能等数据错了才发现 |

**描述**：
`backend/` 目录 6 个源文件（17 个 API 端点 + `indicators.py` 技术指标计算）全部零测试。涉及：
1. ❌ `backend/indicators.py` — MA/RSI/MACD/布林带纯 Python 实现，无单元测试
2. ❌ `backend/routers/market.py` — 6 个端点，无集成测试
3. ❌ `backend/routers/stocks.py` — 6 个端点，无集成测试
4. ❌ `backend/routers/debate.py` — 3 个端点，无集成测试
5. ❌ `backend/routers/trust.py` — 2 个端点，无集成测试

**修复方向**：
1. 优先：`indicators.py` 单元测试（每组指标独立算一遍，和已知结果比对）
2. 其次：market.py + stocks.py 的 HTTP 集成测试（用 httpx.AsyncClient）
3. 最后：debate.py + trust.py 的 Mock 级测试

---

###### TD-037 测试缺乏边界条件/异常路径覆盖

| 属性 | 值 |
|------|-----|
| **分类** | `🧪 testing` `severity:moderate` `module:tests` `impact:可靠性` |
| **发现日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼1d |
| **实盘影响** | 🟡 正常路径能跑，但边界条件下（空输入、None、网络断）的系统行为未验证 |
| **触发场景** | 所有异常/边界路径 |

**描述**：
现有 676 测试主要覆盖"正常路径"，边界条件和异常路径的测试缺失：
1. ❌ 数据源断连模拟测试
2. ❌ 空 DataFrame/空 list 输入测试
3. ❌ LLM 超时/返回非法 JSON 的 fallback 测试

**修复方向**：
在 `tests/` 下建立 `test_boundary/` 子目录，专项覆盖边界条件。
