# 📐 辩论引擎部技术规范

> 扩展 [coding-style.md](../../01-guides/WORKFLOW.md#1-核心原则) 的辩论模块特定规范。

---

## 代码规范

### 编排节点函数签名

```python
# ✅ 正确：每个节点是纯函数，输入 State → 输出 State
def collect_data_node(state: DebateState, collector: DataCollector) -> DebateState:
    """数据采集节点：从数据管道部获取行情/K线/新闻"""
    ...
    return state

# ❌ 禁止：节点内修改外部状态、依赖全局变量
def process(state):
    global cache  # 禁止
    cache["data"] = something  # 禁止
```

### LLM 调用路径

```python
# ✅ 正确：经过基础设施部的 llm.py
from src.utils.llm import LLMService, LLMConfig

service = LLMService()
config = LLMConfig(temperature=0.7, max_tokens=4096)
result = await service.agenerate(prompt, config=config)

# ❌ 禁止：直调 ChatDeepSeek / ChatOpenAI
from langchain_deepseek import ChatDeepSeek  # 禁止
```

### 置信度输出格式

```python
# ✅ 正确：每个分析带置信度
class AnalystOutput(BaseModel):
    reasoning: str = Field(description="分析推理过程")
    score: float = Field(ge=0, le=100, description="评分 0-100")
    confidence: float = Field(ge=0, le=1, description="置信度 0-1")
    evidence: list[str] = Field(description="支撑证据列表")

# ❌ 禁止：纯文本无结构化
return {"analysis": "我觉得这只股票很好"}
```

---

## 文件大小红线

| 文件 | 当前行数 | 红线 | 状态 |
|:-----|:--------:|:----:|:----:|
| `orchestrator.py` | 1622 | **800** | 🔴 **超标！急需拆分** |
| `trust.py` | 759 | **800** | 🟡 接近红线，留意 |
| `models.py` | 368 | **800** | ✅ |
| `reflection.py` | 345 | **800** | ✅ |

### orchestrator.py 拆分计划（Phase 前任务）

```
orchestrator/
├── __init__.py      # 公开 API：DebateOrchestrator
├── graph.py         # LangGraph 图定义 + 边连接
├── nodes/           # 各节点函数，每层一个文件
│   ├── collect.py   # collect_data_node
│   ├── analyst.py   # analyst_round_node
│   ├── review.py    # review_round_node
│   ├── vote.py      # vote_summary_node
│   ├── risk.py      # risk_round_node
│   ├── trader.py    # trader_round_node
│   └── pm.py        # pm_round_node
├── state.py         # DebateState 定义 + 工具函数
└── cost.py          # 费用追踪 + 调用统计
```

---

## 测试规范

### 必须覆盖的场景

- ✅ 每层节点独立测试（data → analyst → review → vote → summary）
- ✅ LLM 调用失败降级（mock LLM 抛异常）
- ✅ 数据空值场景（空行情、空 K 线、空新闻）
- ✅ 历史决策注入偏差（M1 误注入）
- ✅ 信任度分数计算（M3 边界值）
- ✅ 9 层链路端到端（集成测试，可 mock LLM）
- ✅ 辩论结果置信度低于阈值（≤30% 标记不确定）

### Mock 策略

```python
# 使用 tests/test_debate/conftest.py 中的 fixture
# 不要在各测试文件中重复定义

def test_analyst_round_empty_data(sample_debate_input, mocker):
    """验证空数据时分析师不触发 LLM"""
    mock_llm = mocker.patch("src.debate.analysts.LLMService.agenerate")
    result = analyst_round_node(sample_debate_input)
    mock_llm.assert_not_called()  # 短路通过
```

### 覆盖率目标

- 编排器核心逻辑：≥85%
- 信任度模块：≥90%
- 分析师层：≥85%
- 反射模块：≥80%

---

## 性能标准

| 指标 | 目标 | 测量方法 |
|:-----|:----:|:---------|
| 单次完整辩论（9 层） | ≤ 30s | pytest-benchmark |
| LLM 调用次数/辩论 | ≤ 8 次 | CostTracker 统计 |
| 历史注入查询 | ≤ 500ms | 计时装饰器 |
| 信任度计算 | ≤ 100ms | 计时装饰器 |
| 辩论状态序列化 | ≤ 50ms | pytest-benchmark |

---

## 部门间契约

### 数据输入契约（依赖数据管道部）

辩论引擎部期望的 `StockQuote` / `KLine` / `NewsItem` 字段必须包含：

```python
# 辩论引擎部要求的最低字段集
class MinimalQuote(BaseModel):
    code: str        # 股票代码
    price: float     # 最新价
    change_pct: float  # 涨跌幅%
    volume: int      # 成交量
```

如果数据管道部改了这些字段名，辩论引擎部直接崩。

### 数据输出契约（提供给后端 API 部）

```python
class DebateOutput(BaseModel):
    decision: str              # 最终决策：买入/卖出/持有/观望
    confidence: float          # 整体置信度 0-1
    reasoning_summary: str     # 决策理由摘要
    analyst_votes: list[Vote]  # 各大师投票详情
    risk_level: str            # 风险等级
    fetched_at: datetime       # 数据采集时间
```

---

## 审查清单

每次修改辩论引擎代码后自查：

- [ ] LLM 调用都经过 `llm.py`？
- [ ] 所有输出带置信度？
- [ ] 数据空值路径不触发 LLM？
- [ ] token 消耗已记录到 CostTracker？
- [ ] 测试覆盖了失败路径？
- [ ] 跨模块数据契约未改字段名？
- [ ] 新加了节点 → 图定义同步更新？
