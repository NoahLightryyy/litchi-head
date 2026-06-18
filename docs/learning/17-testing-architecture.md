# 17 测试架构与模块自治

## 一句话

> 测试组织方式是代码架构的镜像：**模块化的代码需要模块化的测试**，每个模块有自己的 fixture、自己的 conftest、自己的契约。

---

## 为什么需要它？

### 问题场景

很多项目（包括早期 litchi-head）的测试目录长这样：

```
tests/
├── conftest.py          # 200+ 行，包含所有模块的 fixture
├── test_agents_base.py
├── test_debate_*.py     # 扁平化堆放
└── test_data_*.py
```

flat organize 的痛：
1. **conftest.py 膨胀** — 辩论的 `mock_collector`、知识的 `sample_doc`、Agent 的 `buffett_skill` 全混在一起
2. **不知道 fixture 归谁** — 不敢删，怕影响别的模块，最后变成"只加不减"
3. **模块之间的耦合没测出来** — data 改了模型字段，debate 不知道，编译不报错，运行时炸

### 它的解法

把测试结构做成模块架构的**镜像**：

```
src/                     tests/
├── debate/              ├── test_debate/
│   ├── models.py        │   ├── conftest.py     ← 只放 debate 的 fixture
│   ├── orchestrator.py  │   ├── test_models.py
│   └── trust.py         │   └── test_orchestrator.py
│                        ├── contract/           ← 跨模块契约测试
├── data/                ├── test_data/          ← data 模块独立
│   ├── models.py        │   ├── conftest.py     ← 只放 data 的 fixture
│   └── collector.py     │   └── test_models.py
```

好处：
- **强内聚** — 改 debate 的 fixture，不会碰 data
- **高可见** — 扫一眼 `test_agents/conftest.py` 就知道 Agent 测试需要 mock 什么
- **可组合** — `pytest tests/test_debate/` 只跑辩论模块测试，快

---

## 项目里的真实代码

打开 `docs/01-guides/TESTING_STRATEGY.md`：

```python
# tests/conftest.py —— 只保留"项目级"的共享工具
def make_mock_llm_service(text_response: str = "ok") -> AsyncMock:
    """Mock LLM 工厂（所有模块都可能用）"""
    ...

# tests/test_debate/conftest.py —— 辩论模块专属 fixture
@pytest.fixture
def mock_collector() -> MagicMock:
    """Mock DataCollector，仅 debate 需要"""
    col = MagicMock()
    col.get_realtime_quotes.return_value = []
    return col

# tests/test_backend/conftest.py —— backend 路由测试专属 fixture
@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app)
```

### 三层 fixture 作用域

```
项目级 (tests/conftest.py)
  ├── make_mock_llm_service()  ← 跨模块共享的工具函数
  └── pytest marker 注册

模块级 (tests/test_<模块>/conftest.py)
  ├── mock_collector           ← 仅 debate 使用
  ├── sample_debate_input      ← 仅 debate 使用
  └── auto_clean_temp_dir      ← 仅 memory 使用

文件级 (test_*.py 内部的 fixture)
  └── 仅单个测试文件需要的数据
```

---

## 和传统测试组织有什么不同？

| 对比 | 传统平铺 | 模块镜像 |
|:-----|:---------|:---------|
| fixture 位置 | 全放根 conftest（200+ 行） | 分层放，各管各的 |
| 模块隔离 | 差 — 删 fixture 怕影响别人 | 好 — 删自己 conftest 只影响自己 |
| 跑单模块测试 | 跑全部（慢）或手工 `-k` 过滤 | `pytest tests/test_debate/` |
| 跨模块接口 | 没人管 | `tests/contract/` 专人守着 |
| 新增模块 | 往根 conftest 追加 fixture | 新建 `test_模块/conftest.py` |

---

## 面试会怎么问

> **Q: 你们项目的测试怎么组织的？为什么这么组织？**
>
> A: 我们按模块镜像组织。每个 src/ 下的模块对应 tests/ 下的一个目录，有自己的 conftest.py。
> 这样改一个模块的测试不会影响另一个模块，也能用 `pytest tests/test_模块/` 快速验证单一模块。
> 另外我们还加了 contract/ 目录专门放跨模块的契约测试，确保接口变更时第一时间发现。

> **Q: conftest.py 的作用域规则是什么？**
>
> A: pytest 的 conftest 是目录级别的。根 conftest 的 fixture 对所有测试可见。如果有 fixture 只被一个模块使用，就应该放到那个模块的目录下的 conftest 里，而不是根 conftest。

> **Q: 模块间契约测试怎么写？**
>
> A: 契约测试不 mock，只验证数据格式。比如 data 模块产出 StockQuote，debate 模块消费它，契约测试就构造一个 StockQuote 然后传给 debate 的构造函数，验证能正常工作。不测逻辑，只测接口兼容性。

---

## 自己试试（5 分钟）

1. 打开 `tests/conftest.py`，数数有多少 fixture 和工厂函数
2. 再打开 `tests/test_debate/conftest.py`（如果有的话），对比差异
3. 找出 1 个「只被一个模块使用却放在根 conftest」的 fixture
4. 思考：如果把它移到模块 conftest，会影响哪些测试？
5. 打开 `docs/01-guides/TESTING_STRATEGY.md` 看看完整约定

---

**上一篇：[系统性代码按察 — Silent Failure 审计方法论](16-code-quality-audit.md)**

**下一篇：**（待定）
