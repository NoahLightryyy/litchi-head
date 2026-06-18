# 🧪 litchi-head 测试策略

> **本文档定义项目的测试架构约定、组织方式和质量红线。**
> 每个开发者/AI 在新增或修改测试前应先读本文档。

---

## 1. 测试哲学

### 三大原则

1. **模块自治** — 每个 src/ 模块对应一个测试包，含自己的 `conftest.py`，不依赖其他模块的 fixture
2. **契约优先** — 模块间数据传递（Pydantic models）要有 contract test，改接口必须通知消费者
3. **四层金字塔** — 单元测试 > 集成测试 > API 测试 > E2E 测试，按层级分配精力

```
         ╱  E2E  ╲           ← 5-10%  全流程冒烟
        ╱  API 测试 ╲         ← 10-15% backend 路由
       ╱  集成测试  ╲         ← 15-25% 模块间协作
      ╱   单元测试    ╲       ← 60-70% 纯逻辑 + mock
     ╱─────────────────╲
```

### 纪律

| 纪律 | 说明 |
|:-----|:------|
| **Mock 层不对** | 单元测试 mock 所有外部依赖（LLM / 网络 / 文件系统） |
| **集成测试跑真的** | 集成测试可以 call 真实 API，但要加 `@pytest.mark.integration` |
| **不改测试凑覆盖** | 覆盖率不够 → 补测试，**不**删 `# pragma: no cover` |
| **失败=阻塞** | 任何模块的 CI 测试失败 = 该模块不可发布 |

---

## 2. 文件组织

### 2.1 测试目录结构

```
tests/
├── conftest.py                     # 项目级共享（Mock 工厂 + 全局 fixture）
├── test_sanity.py                  # 冒烟测试 — 验证测试基座自身正常
│
├── test_agents/
│   ├── __init__.py
│   ├── conftest.py                 # ┐ Agent 模块专属 fixture
│   ├── test_base.py                # │ （不存在 → 需要补 ⚠️）
│   ├── test_master_agent.py        # │  当前在 tests/test_agents_base.py 等
│   └── test_xiao_zhi.py           # ┘  建议移入 test_agents/ 目录
│
├── test_backend/
│   ├── __init__.py
│   ├── conftest.py                 # FastAPI TestClient + mock DB
│   ├── test_indicators.py          # ✅ 已有
│   ├── test_market.py              # ❌ 待补
│   ├── test_stocks.py              # ❌ 待补
│   ├── test_debate.py              # ❌ 待补
│   └── test_trust.py               # ❌ 待补
│
├── test_backtest/
│   ├── __init__.py
│   ├── conftest.py                 # 回测专属 fixture
│   ├── test_models.py
│   ├── test_engine.py
│   └── test_bridge.py
│
├── test_data/
│   ├── __init__.py
│   ├── conftest.py                 # Mock DataSource 等
│   ├── test_models.py
│   ├── test_cache.py
│   ├── test_collector.py
│   └── test_providers.py
│
├── test_debate/
│   ├── __init__.py
│   ├── conftest.py                 # Mock LLM + mock collector
│   ├── test_models.py
│   ├── test_orchestrator.py        # （单文件夹已有）
│   └── test_d1～d4_*.py
│
├── test_memory/
│   ├── __init__.py
│   ├── conftest.py                 # 临时目录 fixture
│   ├── test_store.py
│   ├── test_manager.py
│   ├── test_knowledge_base.py
│   └── test_skill_disk.py
│
├── test_risk/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_r1_three_layer.py
│
├── test_trader/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_bridge.py
│   └── test_t1.py
│
├── test_utils/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_llm.py
│   ├── test_cost_tracker.py
│   └── test_complexity_router.py
│
├── contract/                         # 📌 新增：模块间契约测试
│   ├── __init__.py
│   └── test_data_debate_contract.py  # data 输出能被 debate 消费
│
├── e2e/
│   ├── __init__.py
│   ├── conftest.py                 # 完整的全栈启动/关闭
│   └── test_full_pipeline.py
│
└── vcr_config.py                    # VCR 录制配置
```

### 2.2 命名约定

| 元素 | 约定 | 示例 |
|:-----|:------|:------|
| **测试目录** | `test_<模块名>/` | `test_debate/` |
| **测试文件** | `test_<被测模块>.py` | `test_orchestrator.py` |
| **测试类** | `Test<被测组件>` | `TestDebateOrchestratorRun` |
| **测试方法** | `test_<场景>_<预期>` | `test_empty_input_raises` |
| **fixture 文件** | `conftest.py` | 每个测试目录一个 |

### 2.3 当前差距 ⚠️

| 需要改进 | 问题 | 优先级 |
|:---------|:-----|:------:|
| `test_agents/conftest.py` 不存在 | Agent 测试 fixture 混在根 conftest | 🔴 |
| `test_backend/conftest.py` 不存在 | 后端路由测试根本没有目录 | 🔴 |
| `test_data/conftest.py` 不存在 | 数据模块 fixture 在根 conftest | 🟡 |
| `test_memory/conftest.py` 不存在 | 内存模块 fixture 在根 conftest | 🟡 |
| `test_utils/conftest.py` 不存在 | 工具模块 fixture 无归属 | 🟡 |
| `contract/` 目录不存在 | 模块间无契约测试 | 🔴 |
| `e2e/` 目录不存在 | E2E 只有一个文件在根目录 | 🟡 |

---

## 3. fixture 层级约定

### 3.1 三层 fixture 作用域

```
项目级 (tests/conftest.py)
├── 跨模块共享的工具
│   ├── make_mock_llm_service()          ← Mock LLM 工厂
│   ├── make_mock_llm_sequence()
│   ├── make_mock_llm_error()
│   └── 自定义 marker 注册
│
└── 通用 fixture（仅用于冒烟测试）
    ├── mock_llm
    ├── sample_context
    └── sample_result

模块级 (tests/test_<模块>/conftest.py)
├── 本模块的 fixture
│   ├── mock_collector           ← 仅 debate 需要
│   ├── sample_debate_input      ← 仅 debate 需要
│   ├── buffett_skill            ← 仅 debate 需要
│   └── mock_llm_service         ← 覆盖项目级的 mock 逻辑
│
└── 模块级的 autouse fixture
    ├── auto_clean_temp_dir      ← 仅 memory 需要
    └── auto_patch_network       ← 仅 data 需要

测试文件级 (test_*.py 内部的 @pytest.fixture)
└── 仅单个测试文件需要的专用 fixture
```

### 3.2 迁移计划

> 当前所有模块 fixture 都在 `tests/conftest.py`，需要逐步迁移到模块级 conftest。

```
Phase 1: 创建空 conftest + 迁移辩论模块 fixture（~30min）
Phase 2: 迁移 data/memory 模块 fixture（~30min）
Phase 3: 迁移 agent/backtest/risk 模块 fixture（~30min）
Phase 4: 迁移 utils 模块 fixture（~15min）
Phase 5: 创建 contract/ + e2e/ 目录（~15min）
```

---

## 4. 测试类型与 Mock 策略

### 4.1 单元测试（主力，占 60-70%）

| 场景 | Mock 策略 | 示例 |
|:-----|:----------|:------|
| 纯函数计算 | 不 mock | `indicators.py` SMA/RSI/MACD |
| Agent 逻辑 | mock LLMService | `make_mock_llm_service()` |
| 数据模型 | 不 mock，直接构造 | `StockQuote(code=..., price=...)` |
| DataSource | mock 上游数据源 | `MagicMock(spec=DataSourceProtocol)` |
| MemoryStore | mock 文件系统 | `patch("builtins.open")` |

**黄金规则**：单元测试不碰网络、不碰磁盘写（读可以 mock）、不碰 LLM。

### 4.2 集成测试（占 15-25%）

| 场景 | 策略 | marker |
|:-----|:------|:-------|
| 辩论全链路 mock 版 | mock LLM + collector | `@pytest.mark.asyncio` |
| 数据源真实调用 | call akshare 真实 API | `@pytest.mark.integration` |
| LLM 真实调用 | call DeepSeek API | `@pytest.mark.integration` |
| 模块间数据流 | Pydantic serialize→deserialize | `@pytest.mark.unit` |

### 4.3 API 测试（占 10-15%）

```python
# tests/test_backend/conftest.py
@pytest.fixture
def client():
    from backend.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)

# tests/test_backend/test_market.py
class TestMarketEndpoints:
    def test_get_indices(self, client):
        resp = client.get("/api/market/indices")
        assert resp.status_code == 200
        data = resp.json()
        assert "indices" in data
```

### 4.4 E2E 测试（占 5-10%）

```python
# tests/e2e/conftest.py
@pytest.fixture(scope="session")
def full_stack():
    """启动 FastAPI + 等待就绪 → yield → 关闭"""
    ...
```

### 4.5 契约测试（新增）

```python
# tests/contract/test_data_debate_contract.py
"""验证 data 模块的输出能被 debate 模块消费"""
from src.data.models import StockQuote, KLine
from src.debate.models import DebateInput

class TestDataDebateContract:
    def test_stockquote_serves_debate_input(self):
        """data 的 StockQuote 可以构造 DebateInput"""
        quote = StockQuote(code="000001", name="平安银行", price=12.5, ...)
        inp = DebateInput(stock_code=quote.code, stock_name=quote.name)
        assert inp.stock_code == "000001"

    def test_kline_feed_to_analysis(self):
        """data 的 KLine 列表可以作为分析输入"""
        klines = [
            KLine(date="2026-06-01", open=12.0, close=12.5, high=13.0, low=11.8, volume=100000),
        ]
        # debate 消费 KLine 时不应该报错
        prices = [k.close for k in klines]
        assert all(isinstance(p, float) for p in prices)
```

---

## 5. 覆盖率目标

### 5.1 模块级红线

| 模块 | 当前覆盖率 | 目标 | 状态 | 备注 |
|:-----|:---------:|:----:|:----:|:-----|
| `src/utils/` | ~85% | ≥80% | ✅ | |
| `src/core/` | ~80% | ≥80% | ✅ | |
| `src/agents/` | ~82% | ≥80% | ✅ | |
| `src/memory/` | ~78% | ≥80% | 🟡 | 差 2% |
| `src/debate/` | ~92% | ≥80% | ✅ | |
| `src/data/` | ~75% | ≥80% | 🟡 | Provider 层已修复，collector 待补 |
| `src/data/providers/` | 83% | ≥80% | ✅ | 已修复 |
| `src/trader/` | ~70% | ≥80% | 🔴 | |
| `src/risk/` | ~65% | ≥80% | 🔴 | |
| `src/backtest/` | ~75% | ≥80% | 🟡 | |
| `backend/` | 20% | ≥80% | 🔴 | **最短板**，仅 indicators 有测试 |

### 5.2 增量规则

```
新代码必须有测试，否则 CI 门禁拒绝合并：
  ❌ 新增一个 Python 文件无对应测试文件
  ❌ 新增函数、方法无对应测试
  ✅ 纯类型定义（.pyi）、配置、常量可豁免
```

### 5.3 覆盖率测量

```bash
# 单模块测量
pytest tests/test_debate/ --cov=src/debate --cov-report=term-missing

# 全量测量
pytest --cov=src --cov-report=term-missing

# CI 门禁（低于 80% 会失败）
pytest --cov=src --cov-fail-under=80
```

---

## 6. 新增模块的测试 checklist

当向项目添加一个新的 `src/<module>/` 时，必须按以下顺序建立测试：

```
□ 1. 创建 tests/test_<module>/ 目录
□ 2. 创建 __init__.py（空）
□ 3. 创建 conftest.py（模块专属 fixture）
     - 至少一个 autouse fixture 隔离外部依赖
□ 4. 创建 test_models.py（如果模块有数据模型）
□ 5. 每个源文件对应一个测试文件
□ 6. 验证全量覆盖率 ≥ 80%
□ 7. 更新 docs/README.md（如果模块对外暴露接口）
□ 8. 注册到测试金字塔策略文档（可选）
```

---

## 7. 质量门禁（CI）

| 门禁 | 阈值 | 通过标准 |
|:-----|:----:|:---------|
| pytest | 0 failed | 全部测试通过 |
| 覆盖率 | ≥80% | `--cov-fail-under=80` |
| Ruff | 0 error | 代码风格检查 |
| Pyright | 0 error | 类型检查 basic mode |

---

## 8. 常见 FAQ

**Q: 什么时候用 `@pytest.mark.integration`？**
A: 任何需要真实网络/文件 IO 的测试。标记后可通过 `pytest -m "not integration"` 快速跳过。

**Q: 共享 fixture 放在根 conftest 还是模块 conftest？**
A: 如果被 ≥2 个模块共用 → 根 conftest。仅本模块用 → 模块 conftest。

**Q: 需要写测试文档吗？**
A: 每个测试文件顶部的 docstring 写清楚 mock 策略即可，不需要单独文档。

**Q: backend 路由测试怎么测？**
A: 用 FastAPI 的 `TestClient`（同步），mock DataCollector 层，验证 HTTP 状态码 + 响应结构。

**Q: 跨模块接口改了怎么办？**
A: 改之前先看 `tests/contract/` 有没有相关的契约测试，有就先改契约，再改实现。

---

## 9. 相关文档

| 文档 | 说明 |
|:-----|:------|
| [测试债务](debt/TESTING.md) | 测试相关的技术债务追踪 |
| [HANDOVER.md](HANDOVER.md) | 当前进度和增量任务 |
| [ROADMAP.md](../00-overview/ROADMAP.md) | 项目级路线图 |
| [CLAUDE.md](../../CLAUDE.md) | 项目核心纪律（80% 覆盖率红线） |

---

> **最后更新**：2026-06-18（初版 — 测试架构全面梳理）
