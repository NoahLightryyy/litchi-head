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

###### TD-036 `backend/` 测试覆盖不足（17 个 API 端点 + 核心计算逻辑）

| 属性 | 值 |
|------|-----|
| **分类** | `🧪 testing` `severity:critical` `module:backend` `impact:可靠性` |
| **发现日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `🔧 修复中` |
| **本金估算** | ∼2d |
| **实际工时** | ∼4h（indicators.py 100% ✅ + 测试策略文档 ✅） |
| **日利息** | 改 backend 代码全靠手动验证，改了坏了自己不知道 |
| **实盘影响** | 🔴 核心计算（MA/RSI/MACD）已验证，但 5 个路由文件仍无人验证，改错就是亏钱 |
| **触发场景** | 每次 backend 代码变更后 |
| **用户能发现吗** | ❌ 不能 — 测试没发现的问题，用户只能等数据错了才发现 |

**描述**：
`backend/` 目录 6 个源文件（17 个 API 端点 + `indicators.py` 技术指标计算），截至 2026-06-18：
1. ✅ `backend/indicators.py` — 422 行单元测试，100% 覆盖（MA/RSI/MACD/布林带 + 已知序列验证）
2. ❌ `backend/routers/market.py` — 6 个端点，零测试
3. ❌ `backend/routers/stocks.py` — 6 个端点，零测试
4. ❌ `backend/routers/debate.py` — 3 个端点，零测试
5. ❌ `backend/routers/trust.py` — 2 个端点，零测试

**修复方向**：
1. ✅ `indicators.py` 单元测试已完成（422 行，100% 覆盖）
2. 创建 `tests/test_backend/` 目录 + `conftest.py`（TestClient fixture）
3. market.py + stocks.py 的 HTTP 测试（用 fastapi.testclient）
4. debate.py + trust.py 的 Mock 级测试

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

---

###### TD-050 XiaoZhiAgent 无 LLM 错误路径测试

| 属性 | 值 |
|------|-----|
| **分类** | `🧪 testing` `severity:moderate` `module:agents` `impact:可靠性` |
| **发现日期** | 2026-06-18 |
| **发现人** | AI 按察审计 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼30min |
| **日利息** | XiaoZhiAgent 在 LLM 超时/返回非法 JSON 时的行为未验证 |
| **实盘影响** | 🟡 用户问"茅台怎么样"，LLM 超时后 Agent 行为不可预测 |
| **触发场景** | LLM API 超时或返回非结构化内容时 |
| **用户能发现吗** | ❌ 不能 — XiaoZhi 可能返回空内容或崩溃 |

**描述**：
`test_agents_xiao_zhi.py` 只有初始化验证和正常 LLM 回复测试，未覆盖：
1. ❌ LLM 超时（TimeoutError）
2. ❌ LLM 返回非法 JSON
3. ❌ LLM 空响应

---

###### TD-051 MemoryManager 无存储失败测试

| 属性 | 值 |
|------|-----|
| **分类** | `🧪 testing` `severity:moderate` `module:memory` `impact:可靠性` |
| **发现日期** | 2026-06-18 |
| **发现人** | AI 按察审计 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼30min |
| **日利息** | JsonFileStore 磁盘错误会使 MemoryManager 静默失败，行为未验证 |
| **实盘影响** | 🟡 磁盘写满/只读时，记忆系统静默失效，不阻塞但也不工作 |
| **触发场景** | 磁盘空间不足、文件权限错误 |
| **用户能发现吗** | ❌ 不能 — MemoryManager.remember/recall 静默返回 None |

**描述**：
`test_memory_manager.py` 只有 6 个基础 CRUD 测试，存储失败场景完全未覆盖：
1. ❌ 磁盘写入失败（IOError）
2. ❌ 损坏的 JSON 加载
3. ❌ 只读文件系统

---

###### TD-057 Provider 层测试覆盖率严重不足（30-55%）

| 属性 | 值 |
|------|-----|
| **分类** | `🧪 testing` `severity:critical` `module:data` `impact:可靠性` |
| **发现日期** | 2026-06-18 |
| **发现人** | AI 按察审计（首次覆盖率实测） |
| **状态** | `🔧 修复中` |
| **本金估算** | ∼2h |
| **实际工时** | ∼1.5h（2026-06-18 已修复） |
| **日利息** | 数据源是实盘系统第一道关口，Provider 层裸奔意味着「数据可能错、可能慢、可能挂，测试不知道」 |
| **实盘影响** | 🔴 数据源是系统入口，4 个 Provider 平均覆盖率仅 42%。adata 30% 意味着新加入的免费数据源基本没测过 |
| **触发场景** | Provider 实现变更、新数据源接入、Fallback 逻辑修改 |
| **用户能发现吗** | ❌ 不能 — 测试没覆盖的 bug 用户最先发现 |

**描述**：
2026-06-18 首次全量覆盖率实测，Provider 层数据：
| 模块 | 覆盖率 | 风险 |
|:-----|:------:|:----:|
| `src/data/providers/base.py` | 55% | 抽象层协议基础 |
| `src/data/providers/akshare.py` | 46% | 主数据源，一半未测 |
| `src/data/providers/zzshare.py` | 36% | 备用源几乎裸奔 |
| `src/data/providers/adata_source.py` | 30% | 新免费源基本没测 |
| `src/data/providers/fallback.py` | 85% | ✅ 尚可 |

**修复方向**：
1. ✅ `base.py` — 补齐 safe_str/safe_float/safe_int 全部边值测试 → 100%
2. ✅ `akshare.py` — 补 _detect_market 映射 + _row_to_quote/_row_to_kline/_row_to_news + 8 个异常路径 + 资金流向解析 → 90%
3. ✅ `fallback.py` — 补全部委托方法 + 备用也失败的路径 → 100%
4. ✅ `adata_source.py` — 补 _adata_row_to_quote/_adata_row_to_kline + 错误路径 mock 测试 → 83%
5. ⬜ `zzshare.py` — 转换函数已测，方法体需安装 zzshare 后补 → 46%
6. ⬜ `fallback.py` — TD-032 自动恢复逻辑待实现（当前需手动 reset）

---

###### TD-058 缺少模块级 conftest（测试自治性不足）

| 属性 | 值 |
|------|-----|
| **分类** | `🧪 testing` `severity:moderate` `module:tests` `impact:可测试性` |
| **发现日期** | 2026-06-18 |
| **发现人** | AI 测试架构审查 |
| **状态** | `🔧 修复中` |
| **本金估算** | ∼2h |
| **实际工时** | ∼30min（debate 模块示范 ✅） |
| **日利息** | 所有模块 fixture 挤在根 conftest，模块间 fixture 无隔离，改一个模块的 fixture 可能影响其他模块 |
| **实盘影响** | 🟡 不会直接引发实盘问题，但降低开发效率，增加"改测试改出其他模块测试挂了"的风险 |
| **触发场景** | 在根 conftest 修改共享 fixture 时 |
| **用户能发现吗** | ❌ 不能 — 这是内部可测试性问题 |

**描述**：
当前 `tests/conftest.py` 包含了多个模块专属的 fixture（如 `mock_collector`、`sample_debate_input` 等），没有按模块拆分到各自的 `tests/test_<模块>/conftest.py`。

**缺失清单**：
| 目录 | conftest | 依赖根 conftest 的 fixture |
|:-----|:--------:|:-------------------------|
| `test_debate/` | ✅ **示范完成** | `sample_analyses` 已提取到模块 conftest |
| `test_agents/` | ❌ | mock_llm 等已在根 conftest |
| `test_backend/` | ❌ | 无，需要独立的 TestClient fixture |
| `test_data/` | ❌ | 数据 mock 依赖根 conftest |
| `test_memory/` | ❌ | 临时目录 fixture 依赖根 conftest |
| `test_utils/` | ❌ | LLM mock 依赖根 conftest |

**利息分析**：
- 根 conftest 膨胀：当前 299 行，未来每加一个模块继续膨胀
- 模块间耦合：删除/修改一个模块的 fixture 时，不确定是否被其他模块依赖
- 新开发者困惑：不知道 fixture 该放哪里

**修复方向**：
1. 创建各模块的 `tests/test_<模块>/conftest.py`
2. 将模块专属 fixture 从根 conftest 迁移到模块 conftest
3. 根 conftest 只保留跨模块共享的工厂函数（如 `make_mock_llm_service`）
4. 参考 `docs/01-guides/TESTING_STRATEGY.md` §3 fixture 层级约定

---

###### TD-059 缺少模块间契约测试

| 属性 | 值 |
|------|-----|
| **分类** | `🧪 testing` `severity:moderate` `module:tests` `impact:可靠性` |
| **发现日期** | 2026-06-18 |
| **发现人** | AI 测试架构审查 |
| **状态** | `✅ 已修复` |
| **本金估算** | ∼1h |
| **修复日期** | 2026-06-18 |
| **修复说明** | `tests/contract/test_data_to_debate.py` — data→debate 4 项契约测试（JSON roundtrip + format_market_brief） |
| **日利息** | data 模块改了模型字段，debate 模块不知道→运行时才炸；没有防御层 |  |
| **实盘影响** | 🟡 模块间接口变更无法被早期发现，上升到集成测试层才发现 |
| **触发场景** | 跨模块数据模型字段变更（改名/删除/类型改变） |
| **用户能发现吗** | ❌ 不能 — 编译/运行时错误才会暴露，用户可能直接看到 500 |

**描述**：
项目有 8 个 Python 模块，模块间通过 Pydantic 模型传递数据，但没有任何契约测试验证：
- data → debate 的数据流（StockQuote/KLine 被 debate 消费）
- debate → trader 的数据流（AgentAnalysis 被 trader 消费）
- trader → backtest 的数据流（TradePlan 被 backtest 消费）

**利息分析**：
- 当前靠"改完了跑全部测试"来发现跨模块问题，但不一定覆盖所有消费者
- Pydantic 模型字段别名、默认值、类型变化都可能无声地破坏下游

**修复方向**：
1. 创建 `tests/contract/` 目录
2. 为每对跨模块数据流写契约测试
3. 契约测试在 CI 中优先执行（最快反馈循环）
4. 参考 `docs/01-guides/TESTING_STRATEGY.md` §4.5

---

###### TD-060 测试架构无文档化约定

| 属性 | 值 |
|------|-----|
| **分类** | `🧪 testing` `severity:low` `module:tests` `impact:可维护性` |
| **发现日期** | 2026-06-18 |
| **发现人** | AI 测试架构审查 |
| **状态** | `🔧 修复中` |
| **本金估算** | ∼1h |
| **实际工时** | ∼30min（`docs/01-guides/TESTING_STRATEGY.md` 已创建 ✅） |
| **日利息** | 新增模块测试无规范可循，全凭个人经验 |
| **实盘影响** | 🟢 低 — 不影响运行，但影响团队（含 AI）的测试效率和一致性 |
| **触发场景** | 新增模块/改动测试结构时 |
| **用户能发现吗** | ❌ 不能 |

**描述**：
项目没有一个地方系统性地描述：
- 测试文件怎么组织
- fixture 放哪里
- 各层测试的 mock 策略是什么
- 覆盖率目标是什么
- 新增模块时测试 checklist

**修复方向**：
1. ✅ `docs/01-guides/TESTING_STRATEGY.md` 已创建
2. ⬜ 在 CLAUDE.md 中添加测试策略文档的索引引用
3. ⬜ 新开发者/AI 上手时，先读此文档再写测试

---

###### TD-052 零错误日志验证测试

| 属性 | 值 |
|------|-----|
| **分类** | `🧪 testing` `severity:moderate` `module:tests` `impact:可观测性` |
| **发现日期** | 2026-06-18 |
| **发现人** | AI 按察审计 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼1h |
| **日利息** | 错误日志是否正确输出完全不可见，日志配置错了也不知道 |
| **实盘影响** | 🟡 日志系统配置错误→出问题没人知道→变成静默失败 |
| **触发场景** | 任何异常路径 — 测试验证了逻辑但没验证日志 |
| **用户能发现吗** | ❌ 不能 — 日志是内部可观测性工具 |

**描述**：
所有测试只验证业务逻辑结果（返回值/异常），未使用 `caplog` 验证错误日志是否输出：
1. ❌ 无测试验证 `logger.exception()` 被调用
2. ❌ 无测试验证错误消息包含异常描述
3. ❌ 无测试验证 `AgentLogger` 日志格式正确
