# Data → Debate 接驳 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让投资大师在辩论中看到结构化的市场数据（行情 + K 线 + 新闻），实现端到端分析链路

**Architecture:** 在 `src/data/collector.py` 中新增纯函数 `format_market_brief()`，将过滤后的个股数据格式化为自然语言简报文本；在 `collect_data_node` 中调用此函数并拼入大师的 question；同时将原始结构化数据存入 `AgentContext.input_data` 供后续使用。

**Tech Stack:** Python 3.12+ / Pydantic / akshare

---

### Task 1: `format_market_brief()` 函数 + 测试

**Files:**
- Modify: `src/data/collector.py` — 新增 `format_market_brief()`
- Test: `tests/test_data_collector.py` — 追加 `TestFormatMarketBrief` 类

- [ ] **Step 1.1: 写测试 — 完整数据场景**

在 `tests/test_data_collector.py` 末尾追加：

```python
# ── Tests: format_market_brief ─────────────────────────────────────────


class TestFormatMarketBrief:
    """format_market_brief 函数验证"""

    def test_full_data(self):
        """提供完整行情+K线+新闻"""
        from src.data.collector import format_market_brief
        from src.data.models import KLine, NewsItem, StockQuote

        quote = StockQuote(
            code="000001", name="平安银行", price=12.50,
            change_pct=2.46, volume=1000000, change=0.30, amount=1.25e7,
            high=12.80, low=12.30, open_=12.40, prev_close=12.20,
        )
        klines = [
            KLine(date="2026-06-05", open=12.40, close=12.50, high=12.80, low=12.30, volume=500000, amount=6.25e6),
            KLine(date="2026-06-04", open=12.30, close=12.35, high=12.50, low=12.20, volume=450000, amount=5.58e6),
            KLine(date="2026-06-03", open=12.10, close=12.20, high=12.30, low=12.05, volume=400000, amount=4.88e6),
        ]
        news = [
            NewsItem(code="000001", title="平安银行发布年报", date="2026-06-05", source="东方财富"),
            NewsItem(code="000001", title="平安银行数字化转型", date="2026-06-04", source="证券时报"),
        ]

        result = format_market_brief(
            stock_code="000001",
            stock_name="平安银行",
            quote=quote,
            klines=klines,
            news=news,
        )

        assert "📊 市场简报 — 平安银行 (000001)" in result
        assert "最新价 12.50 元" in result
        assert "涨幅 +2.46%" in result
        assert "平安银行发布年报" in result
        assert "平安银行数字化转型" in result

    def test_no_data(self):
        """无任何数据"""
        from src.data.collector import format_market_brief

        result = format_market_brief(
            stock_code="000001",
            stock_name="平安银行",
        )

        assert "暂无可用数据" in result

    def test_quote_only(self):
        """仅行情数据（无K线/新闻）"""
        from src.data.collector import format_market_brief
        from src.data.models import StockQuote

        quote = StockQuote(
            code="000001", name="平安银行", price=12.50,
            change_pct=2.46, volume=1000000, change=0.30, amount=1.25e7,
            high=12.80, low=12.30, open_=12.40, prev_close=12.20,
        )

        result = format_market_brief(
            stock_code="000001", stock_name="平安银行", quote=quote,
        )

        assert "实时行情" in result
        assert "暂无可用数据" not in result

    def test_no_news(self):
        """有行情+K线但无新闻"""
        from src.data.collector import format_market_brief
        from src.data.models import KLine, StockQuote

        quote = StockQuote(
            code="000001", name="平安银行", price=12.50,
            change_pct=2.46, volume=1000000, change=0.30, amount=1.25e7,
            high=12.80, low=12.30, open_=12.40, prev_close=12.20,
        )
        klines = [
            KLine(date="2026-06-05", open=12.40, close=12.50, high=12.80, low=12.30, volume=500000, amount=6.25e6),
            KLine(date="2026-06-04", open=12.30, close=12.35, high=12.50, low=12.20, volume=450000, amount=5.58e6),
        ]
        result = format_market_brief(
            stock_code="000001", stock_name="平安银行", quote=quote, klines=klines,
        )

        assert "实时行情" in result
        assert "近期走势" in result
        assert "新闻" not in result

    def test_empty_stock_name(self):
        """股票名为空时降级"""
        from src.data.collector import format_market_brief

        result = format_market_brief(stock_code="000001", stock_name="")

        assert "000001" in result
        assert "暂无可用数据" in result
```

- [ ] **Step 1.2: 跑测试验证失败**

```bash
cd d:/HuaweiMoveData/Users/HUAWEI/Desktop/litchi-head-1 && python -m pytest tests/test_data_collector.py::TestFormatMarketBrief -v
```
Expected: 全部 5 个 FAIL — `ImportError: cannot import name 'format_market_brief' from 'src.data.collector'`

- [ ] **Step 1.3: 实现 format_market_brief()**

在 `src/data/collector.py` 末尾（`__all__` 之前）追加：

```python
def format_market_brief(
    stock_code: str,
    stock_name: str,
    quote: StockQuote | None = None,
    klines: list[KLine] | None = None,
    news: list[NewsItem] | None = None,
) -> str:
    """生成市场简报文本

    将结构化行情/K线/新闻数据格式化为自然语言段落，
    供 LLM 直接消费。

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        quote: 个股实时行情（已过滤）
        klines: K 线数据
        news: 新闻列表

    Returns:
        格式化文本，以 "📊 市场简报" 开头
    """
    if stock_name:
        header = f"📊 市场简报 — {stock_name} ({stock_code})"
    else:
        header = f"📊 市场简报 — {stock_code}"

    lines = [header]
    lines.append("━" * 30)
    has_data = False

    # ── 实时行情 ──
    if quote is not None:
        has_data = True
        parts = [f"最新价 {quote.price:.2f} 元"]
        if quote.change_pct:
            parts.append(f"涨幅 {quote.change_pct:+.2f}%")
        parts.append(f"成交量 {quote.volume:,} 手")
        lines.append("【实时行情】" + " | ".join(parts))

    # ── 近期走势（基于 K 线） ──
    if klines and len(klines) >= 2:
        has_data = True
        closes = [k.close for k in klines if k.close > 0]
        if len(closes) >= 2:
            avg_price = sum(closes) / len(closes)
            # closes[0] = 最新, closes[-1] = 最早
            lines.append(
                f"【近期走势】近 {len(klines)} 个交易日 | "
                f"收盘价 {closes[-1]:.2f} → {closes[0]:.2f} | "
                f"均价 {avg_price:.2f}"
            )

    # ── 关键价位 ──
    if quote is not None:
        has_data = True
        parts = []
        if quote.open_:
            parts.append(f"今开 {quote.open_:.2f}")
        if quote.prev_close:
            parts.append(f"昨收 {quote.prev_close:.2f}")
        if quote.high:
            parts.append(f"最高 {quote.high:.2f}")
        if quote.low:
            parts.append(f"最低 {quote.low:.2f}")
        if parts:
            lines.append("【关键价位】" + " | ".join(parts))

    # ── 新闻摘要 ──
    if news:
        has_data = True
        news_lines = [f"【新闻摘要】（{min(len(news), 5)} 条）"]
        for n in news[:5]:
            news_lines.append(f"  • {n.title or '(无标题)'}")
        lines.extend(news_lines)

    if not has_data:
        lines.append("暂无可用数据")

    return "\n".join(lines)
```

并在文件末尾追加 `format_market_brief` 到 `__all__`：

```python
__all__ = ["DataCollector", "format_market_brief"]
```

- [ ] **Step 1.4: 跑测试验证通过**

```bash
cd d:/HuaweiMoveData/Users/HUAWEI/Desktop/litchi-head-1 && python -m pytest tests/test_data_collector.py::TestFormatMarketBrief -v
```
Expected: 全部 5 个 PASS

- [ ] **Step 1.5: 提交**

```bash
cd d:/HuaweiMoveData/Users/HUAWEI/Desktop/litchi-head-1 && git add tests/test_data_collector.py src/data/collector.py && git commit -m "feat: add format_market_brief() for market data text summarization

新增 format_market_brief() 纯函数，将结构化行情/K线/新闻格式化
为自然语言简报文本，供 LLM 直接消费。

- 行情：最新价、涨跌幅、成交量
- K线：n日涨跌方向、均价
- 新闻：前5条标题摘要
- 支持降级：无数据时显示'暂无可用数据'

5 个测试覆盖完整/空/部分数据场景

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 修改 `collect_data_node` — 行情过滤 + 简报生成

**Files:**
- Modify: `src/debate/orchestrator.py` — collect_data_node
- Test: `tests/test_debate_orchestrator.py` — 追加新测试

- [ ] **Step 2.1: 写测试 — 验证 brief 和 quote 字段**

在 `tests/test_debate_orchestrator.py` 中 `TestCollectDataNode` 类末尾追加：

```python
    def test_collect_data_node_has_brief(self, mock_collector):
        """market_data 包含 brief 和 quote 字段"""
        state: DebateState = {
            "session_id": "test-brief",
            "debate_input": {
                "stock_code": "000001",
                "stock_name": "平安银行",
            },
            "current_round": 0,
            "analyses": {},
            "market_data": {},
            "vote_summary": {},
            "errors": [],
        }
        result = collect_data_node(state, mock_collector)
        md = result["market_data"]
        assert "brief" in md, "缺少 brief 字段"
        assert isinstance(md["brief"], str), "brief 应为字符串"
        assert len(md["brief"]) > 0, "brief 不应为空"
        # mock collector 返回空列表 → 简报应为"暂无可用数据"
        assert "暂无可用数据" in md["brief"]
        # quote 应为 None（空数据时）
        assert md["quote"] is None
```

- [ ] **Step 2.2: 跑测试验证失败**

```bash
cd d:/HuaweiMoveData/Users/HUAWEI/Desktop/litchi-head-1 && python -m pytest tests/test_debate_orchestrator.py::TestCollectDataNode::test_collect_data_node_has_brief -v
```
Expected: FAIL — `assert "brief" in md` fails because brief key doesn't exist yet

- [ ] **Step 2.3: 修改 collect_data_node**

替换 `src/debate/orchestrator.py` 中 `collect_data_node` 函数的 `return` 部分。

当前：
```python
    return {
        "market_data": {
            "quotes": [q.model_dump() for q in quotes],
            "klines": [k.model_dump() for k in klines],
            "news": [n.model_dump() for n in news],
        },
    }
```

改为：
```python
    # 按个股过滤行情
    target_quote: StockQuote | None = None
    for q in quotes:
        if q.code == code:
            target_quote = q
            break

    # 生成市场简报
    brief = format_market_brief(
        stock_code=code,
        stock_name=inp.get("stock_name", ""),
        quote=target_quote,
        klines=klines,
        news=news,
    )

    return {
        "market_data": {
            "brief": brief,
            "quote": target_quote.model_dump() if target_quote else None,
            "quotes": [q.model_dump() for q in quotes],
            "klines": [k.model_dump() for k in klines],
            "news": [n.model_dump() for n in news],
        },
    }
```

同时在 orchestrator.py 的 import 部分添加 `format_market_brief`：

当前：
```python
from src.data.collector import DataCollector
```

改为：
```python
from src.data.collector import DataCollector, format_market_brief
```

- [ ] **Step 2.4: 跑测试验证通过**

```bash
cd d:/HuaweiMoveData/Users/HUAWEI/Desktop/litchi-head-1 && python -m pytest tests/test_debate_orchestrator.py::TestCollectDataNode -v
```
Expected: 全部 PASS（原有 2 个 + 新增 1 个）

- [ ] **Step 2.5: 提交**

```bash
cd d:/HuaweiMoveData/Users/HUAWEI/Desktop/litchi-head-1 && git add src/debate/orchestrator.py tests/test_debate_orchestrator.py && git commit -m "feat: collect_data_node 按个股过滤行情并生成市场简报

- collect_data_node 新增行情过滤（quotes → target_quote）
- 在 market_data 中新增 brief 文本和 quote 结构化字段
- format_market_brief 对空数据降级输出'暂无可用数据'

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 修改 `_run_single_master` — 简报拼入 question + 结构化数据下传

**Files:**
- Modify: `src/debate/orchestrator.py` — `_run_single_master()`

- [ ] **Step 3.1: 修改 _run_single_master**

替换 `src/debate/orchestrator.py` 中 `_run_single_master` 函数的问题增强逻辑。

当前（约第 117-124 行）：
```python
    # 构建增强问题（附加上下文）
    enhanced = question
    news_list = market_data.get("news", [])
    if news_list:
        news_summary = "\n".join(
            [f"- {n.get('title', '')}" for n in news_list[:5]]
        )
        enhanced += f"\n\n相关新闻：\n{news_summary}"
```

改为：
```python
    # 构建增强问题（附加上下文）
    enhanced = question
    brief = market_data.get("brief", "")
    if brief:
        enhanced += f"\n\n📊 以下为当前市场数据：\n{brief}"
```

同时在 `ctx.input_data` 中追加 `market_data`：

当前：
```python
        ctx = AgentContext(
            session_id=session_id,
            input_data={
                "question": enhanced,
                "stock_code": stock_code,
                "stock_name": stock_name,
            },
```

改为：
```python
        ctx = AgentContext(
            session_id=session_id,
            input_data={
                "question": enhanced,
                "stock_code": stock_code,
                "stock_name": stock_name,
                "market_data": market_data,
            },
```

- [ ] **Step 3.2: 跑全部 debate 测试**

```bash
cd d:/HuaweiMoveData/Users/HUAWEI/Desktop/litchi-head-1 && python -m pytest tests/test_debate_orchestrator.py -v
```
Expected: 全部 PASS（现有的 master_round 测试中 `_run_single_master` 被 mock，不受影响；`market_data.get("brief", "")` 安全降级）

- [ ] **Step 3.3: 提交**

```bash
cd d:/HuaweiMoveData/Users/HUAWEI/Desktop/litchi-head-1 && git add src/debate/orchestrator.py && git commit -m "feat: _run_single_master 接入市场简报 + 结构化下传

- question 拼入 format_market_brief 生成的文本简报（替代纯新闻标题）
- AgentContext.input_data 附带 market_data 结构化字段供后续使用
- 向后兼容：market_data 无 brief 时行为不变

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 全量验证 + 推送

**Files:**
- N/A（仅运行检查命令）

- [ ] **Step 4.1: Ruff 检查**

```bash
cd d:/HuaweiMoveData/Users/HUAWEI/Desktop/litchi-head-1 && ruff check src/data/collector.py src/debate/orchestrator.py
```
Expected: 0 errors

- [ ] **Step 4.2: Pyright 类型检查**

```bash
cd d:/HuaweiMoveData/Users/HUAWEI/Desktop/litchi-head-1 && pyright src/data/collector.py src/debate/orchestrator.py
```
Expected: 0 errors

- [ ] **Step 4.3: 全量测试**

```bash
cd d:/HuaweiMoveData/Users/HUAWEI/Desktop/litchi-head-1 && python -m pytest tests/ -v --tb=short
```
Expected: 所有测试通过（300+ passed, 4 skipped）

- [ ] **Step 4.4: 推送到远程**

```bash
cd d:/HuaweiMoveData/Users/HUAWEI/Desktop/litchi-head-1 && git push
```
Expected: 推送成功，远程 branch 同步
