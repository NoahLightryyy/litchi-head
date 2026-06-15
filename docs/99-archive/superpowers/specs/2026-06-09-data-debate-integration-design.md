# Data → Debate 接驳设计文档

> data 模块（DataCollector）与 debate 模块（DebateOrchestrator）的集成设计
> 目标：让投资大师在辩论中看到结构化的市场数据，实现端到端分析链路

---

## 1. 现状分析

### 当前已有的接驳

`DebateOrchestrator.collect_data_node` 已调用 `DataCollector` 采集三类数据：

| 数据 | 采集方式 | 当前用途 |
|:----|:---------|:---------|
| 实时行情 | `get_realtime_quotes()` → 全市场 | 存 `market_data["quotes"]`，但未被大师使用 |
| K 线 | `get_klines(code)` | 存 `market_data["klines"]`，未被大师使用 |
| 新闻 | `get_news(code)` | 仅前 5 条标题拼入问题文本 |

### 现存问题

1. **全市场行情未过滤** — `get_realtime_quotes()` 拉取沪深~5000 只股票，只分析 1 只的情况下浪费
2. **数据有采集无加工** — K 线/行情的结构化数据未格式化，大师的 LLM 收不到这些信息
3. **缺乏端到端验证** — 未在真实环境中跑通过完整链路

---

## 2. 设计目标

- ✅ 按个股过滤行情数据，降低传输和令牌消耗
- ✅ 将行情 + K 线 + 新闻格式化为自然语言"市场简报"，让大师快速理解市场状态
- ✅ 结构化数据也保留，供未来深度分析使用
- ✅ 纯函数设计，可测试
- ✅ 不改动现有模块的接口契约（DebateInput / AgentAnalysis / DebateResult）

---

## 3. 架构设计

### 3.1 数据流（修改后）

```
┌──────────────┐    ┌───────────────────┐    ┌──────────────────┐
│  collect_data │    │  format_market_   │    │  _run_single_    │
│  _node        │───→│  brief()          │───→│  master          │
│               │    │                   │    │                  │
│ ① 采集行情    │    │ ④ 行情过滤       │    │ ⑥ question +=   │
│ ② 采集K线     │    │ ⑤ 生成市场简报    │    │    📊 市场数据…  │
│ ③ 采集新闻    │    │   文本 + 结构化   │    │ ⑦ 追加到        │
│               │    │                   │    │    input_data    │
└──────────────┘    └───────────────────┘    └──────────────────┘
                           │
                           ▼
                    market_data = {
                      "brief": "📊 文本摘要…",
                      "quote": StockQuote{...},
                      "klines": [...],
                      "news": [...]
                    }
```

### 3.2 新增函数：`format_market_brief()`

位置：`src/data/collector.py`

```python
def format_market_brief(
    stock_code: str,
    stock_name: str,
    quote: StockQuote | None = None,
    klines: list[KLine] | None = None,
    news: list[NewsItem] | None = None,
) -> str:
    """生成市场简报文本

    将结构化数据格式化为自然语言段落，供 LLM 直接消费。

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        quote: 个股实时行情（已过滤）
        klines: K 线数据（按日期降序，最新在前）
        news: 新闻列表（按时间降序，最新在前）

    Returns:
        格式化文本，以 "📊 市场简报" 开头
    """
```

### 3.3 简报模板

```
📊 市场简报 — {stock_name} ({stock_code})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【实时行情】最新价 {price} 元 | 涨幅 {change_pct}% | 成交额 {amount} 亿
【近期走势】5 日涨跌幅 {period_5d}% | 20 日涨跌幅 {period_20d}%
【关键价位】今开 {open} | 昨收 {prev_close} | 最高 {high} | 最低 {low}
【新闻摘要】（{count} 条）
  • {title_1}
  • {title_2}
```

- 无数据时输出：`📊 市场简报 — {stock_name} ({stock_code}): 暂无可用数据`

### 3.4 修改 `collect_data_node`

```python
def collect_data_node(state, collector):
    # …原有采集逻辑不变…

    # 🆕 按个股过滤行情
    target_quote = None
    for q in quotes:
        if q.code == code:
            target_quote = q
            break

    # 🆕 生成市场简报
    brief = format_market_brief(
        stock_code=code,
        stock_name=inp.get("stock_name", ""),
        quote=target_quote,
        klines=klines,
        news=news,
    )

    return {
        "market_data": {
            "brief": brief,          # 🆕 文本摘要
            "quote": target_quote.model_dump() if target_quote else None,
            "klines": [k.model_dump() for k in klines],
            "news": [n.model_dump() for n in news],
        },
    }
```

### 3.5 修改 `_run_single_master`

```python
# 增强问题：拼入市场简报
enhanced = question
brief = market_data.get("brief", "")
if brief:
    enhanced = f"{question}\n\n📊 以下为当前市场数据：\n{brief}"

# 结构化数据也传入 context，供未来使用
ctx = AgentContext(
    …,
    input_data={
        "question": enhanced,
        "market_data": market_data,  # 🆕 附带结构数据
        …,
    },
)
```

---

## 4. 修改文件清单

| 文件 | 操作 | 说明 |
|:----|:----|:------|
| `src/data/collector.py` | **🆕 新增** `format_market_brief()` | 纯函数，生成市场简报 |
| `src/debate/orchestrator.py` | **🔧 修改** `collect_data_node` | 行情过滤 + 调用 format_market_brief |
| `src/debate/orchestrator.py` | **🔧 修改** `_run_single_master` | 简报拼入 question + 结构化数据传 input_data |
| `tests/test_data_collector.py` | **🆕 追加** `test_format_market_brief_*` | 5 个测试用例 |
| `tests/test_debate_orchestrator.py` | **🔧 补充** `test_collect_data_node_brief` | 验证 brief 生成 |

---

## 5. 测试计划

### 单元测试（`test_data_collector.py` 追加）

| 测试 | 场景 | 验证 |
|:----|:----|:-----|
| `test_format_market_brief_full` | 提供完整行情+K线+新闻 | 输出含预期格式 |
| `test_format_market_brief_no_data` | 全部为空/None | 输出"暂无可用数据" |
| `test_format_market_brief_quote_only` | 仅行情 | 输出含行情简报 |
| `test_format_market_brief_no_news` | 无新闻 | 简报不含新闻段落 |

### 编排器测试（`test_debate_orchestrator.py` 补充）

| 测试 | 场景 | 验证 |
|:----|:----|:-----|
| `test_collect_data_node_brief_in_market_data` | collect_data_node 执行 | market_data 含 "brief" 字段 |

---

## 6. 不做的事情

- ❌ 不修改 MasterAgent（由 question 文本 + input_data 间接接收数据）
- ❌ 不修改 data/models.py（现有 Pydantic 模型够用）
- ❌ 不修改 debate/models.py（DebateInput/DebateResult 不变）
- ❌ 不加新模块/新类
- ❌ 不加技术指标计算（均线/RSI 等，Phase 2 再说）

---

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|:----|:----:|:----:|:-----|
| akshare 在代理环境不可用 | 中 | 集成测试 skip | 单元测试纯函数，不依赖网络 |
| 市场简报长度超 token | 低 | 中 | 默认截断：K线最多 20 行，新闻最多 5 条 |
| 过滤行情找不到匹配 | 低 | 低 | 退化为仅显示 stock_name 的简报 |

---

> **文档版本**：v1.0
> **创建日期**：2026-06-09
> **状态**：✅ 已批准
