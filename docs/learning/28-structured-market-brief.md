---
number: 28
title: 结构化多层市场简报 — 让 LLM "看什么股说什么话"
---

# 结构化多层市场简报 — 让 LLM "看什么股说什么话"

## 一句话

把一个股票的数据分成 5 层（行情/行业分析/新闻/情绪/基本面）结构化注入 LLM prompt，让大师和分析师自动获得行业上下文，无需每改一个行业就跑一次 prompt。

## 项目里的对应

- **核心函数**：[`format_market_brief()`](../../src/data/collector.py) — 生成结构化简报
- **注入点**：[`collect_data_node()`](../../src/debate/orchestrator.py) — 数据采集节点
- **消费端**：`_run_analyst()`、`_run_single_master()`、`_run_rebuttal()`、`_run_independent_review()` 全部通过 `market_data["brief"]` 自动获取
- **行业数据来源**：[`DynamicIndicatorSelector`](../../src/data/indicators/selector.py) + [`REGISTRY`](../../src/data/indicators/registry.py)

## 问题

> 平安银行是金融股，看的是 PE/PB/ROE/坏账率。
> 茅台是消费股，看的是毛利率/净利率/营收增长率。
> 给所有大师塞**同样 17 个财务指标**，他们得自己判断"哪些指标可能重要"，而非直接知道行业标准是什么。

## 解决方案

### 结构

```
📊 市场简报 — 平安银行 (000001)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

----- 行情层 -----
最新价 12.50 元 | 涨幅 +2.46% | ...

----- 行业分析层 -----              ← PD-005 新增
所属行业: 银行
产业链位置: 金融行业
关键指标:
  • 市盈率: 股价/每股收益（正常范围 10-20倍）
  • 市净率: 股价/每股净资产（正常范围 1-3倍）
  • ...

----- 新闻层 -----
• 平安银行发布年报
...

----- 情绪层 -----
（暂无情绪数据）

----- 基本面层 -----
最新报告期: 2024-12-31
📊 每股指标: EPS 1.25 元 | ...
```

### 设计要点

1. **分层独立** — 每层用 `----- 层名 -----` 视觉分隔。LLM 处理长文本时会自动聚焦，分层让它能快进到需要的部分。
2. **向后兼容** — `format_market_brief()` 新增参数有默认值，旧调用不改。
3. **一次性注入** — 行业数据只在 `collect_data_node` 拉一次，后续所有 LLM 调用无额外成本。

### 数据流

```
collect_data_node()
  ├── quotes / klines / news / financials
  ├── get_dynamic_indicators(code)    ← 1 次 API 调用
  │     ├── industry: "银行"
  │     ├── chain_position: "financial"
  │     └── indicators: [{id, name, description, ...}]
  └── format_market_brief(..., 3 个新参数)
        └── brief 字符串 → market_data["brief"]

→ _run_single_master(market_data=market_data)
    → brief = market_data.get("brief", "")
    → prompt += f"...当前市场数据：\n{brief}"
    → LLM 收到完整的分层简报
```

## 为什么这比"传额外参数"好

| 方案 | 问题 |
|:-----|:-----|
| 每个大师传 `industry` 参数 | 改接口，改测试，改 7 个大师调用点 |
| 在 prompt 里拼接行业字符串 | 每个调用点都得改，容易漏 |
| 新增一个分区注入 `market_data["brief"]` | **改一处，全生效** |

## 关键代码

```python
# collect_data_node 中的新逻辑（~15 行）
try:
    di = collector.get_dynamic_indicators(code)
    if di:
        industry_name = str(di.get("industry", ""))
        chain_pos = str(di.get("chain_position", ""))
        key_indicators = list(di.get("indicators", []) or [])
except Exception:
    logger.exception("动态指标获取失败")

# 传给 format_market_brief，其他参数不变
brief = format_market_brief(
    ...,  # 原有参数不变
    industry=industry_name,
    chain_position=chain_pos,
    key_indicators=key_indicators,
)
```

## 自己试试

1. 打开 `src/data/collector.py`，找到 `format_market_brief()` 函数里的行业分析层代码
2. 把 `key_indicators` 改成空列表，看看输出变成什么样
3. 在 `src/debate/orchestrator.py` 的 `collect_data_node()` 里，注释掉 `get_dynamic_indicators()` 调用，运行测试 `test_collect_data_node_with_industry`，看看失败原因 — 理解为什么测试在验证行业数据

## 前置卡片

- [27 PD 动态指标体系](27-pd-dynamic-indicators.md) — 行业注册表 + 动态选择器（PD-005 的数据来源）
- [11 多 Agent 辩论系统](11-multi-agent-debate.md) — 辩论编排器的整体设计
