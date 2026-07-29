# 功能模块：数据采集

> 多数据源行情/新闻/财务数据的获取、缓存、标准化。

## 模块定义

多数据源行情/新闻/财务数据的获取、缓存、标准化。

**职责边界**：
- ✅ 多个数据源的统一接入（A股、港美股、加密货币等）
- ✅ 数据缓存与过期策略
- ✅ 原始数据 → Pydantic 模型的标准化转换
- ✅ **基本面指标采集** — 财务指标（ROE/毛利率/负债率等）、产业链定位
- ❌ 不负责数据的深度分析（那是辩论模块的事）
- ❌ 不负责因子计算（那是因子研究模块的事）
- ❌ 不负责供应链客户/供应商解析（NLP Pipeline 当期独立评估）

## 代码结构

| 文件 | 说明 |
|------|------|
| `src/data/collector.py` | 主采集器，封装 akshare 调用 |
| `src/data/evidence.py` | 多源身份、能力、六态结果、注册与完整性评估 |
| `src/data/evidence_service.py` | 多通道并发采集、异常显式化、同上游去重与统一信封 |
| `src/data/models.py` | Pydantic 数据模型（StockInfo / KLine / NewsItem / StockQuote） |
| `src/data/cache.py` | 缓存层（带 TTL） |
| `src/data/providers/cninfo.py` | 巨潮资讯权威公告适配器（公开端点直连 + AKShare 可替换实现） |

## 架构（当前状态）

```
旧链路（仍在运行）：
DataCollector → DataSource → AKShare/AData/ZzShare/Fallback
                           └─ 失败仍可能被压成 [] / None

新契约（汇总层完成，待逐源接入）：
DataEvidenceService
  → 并发调用多个 EvidenceSource
  → 按 capability 汇总并统一打包为业务节点输入
  → EvidenceSourceRegistry
      → SourceDescriptor（适配器身份 + 真实 upstream_id + capabilities）
      → SourceResult（SUCCESS_DATA / SUCCESS_EMPTY / FAILED /
                      UNSUPPORTED / STALE / CONFLICTED）
  → EvidencePolicy
      → 按独立 upstream_id 判断完整性
      → discovery_only 来源不计入证据门槛
```

### 多源完整性不变量

1. 同一个真实上游即使有多个适配器，也只算一个独立来源；
2. `SUCCESS_EMPTY` 只表示上游成功完成查询并明确返回零条；
3. 网络、解析和权限错误必须返回 `FAILED`，不能伪装成空数据；
4. RSSHub 等发现型来源标记为 `discovery_only`，不参与证据门槛；
5. 强制上游和独立来源数任一不足，评估结果均为 `complete=False`；
6. 汇总层只能传递统一证据模型、来源状态、时间范围和完整性结果，业务节点不依赖
   CNINFO、AKShare 等具体通道名称；
7. 当前契约尚未接管旧 Provider 或正式辩论图，因此 TD-069 仍未关闭。

## 数据契约（关键模型）

| 模型 | 说明 |
|------|------|
| `StockInfo` | 股票基本信息（代码、名称、行业等） |
| `KLine` | K 线数据（开高低收、成交量等） |
| `NewsItem` | 新闻条目（标题、时间、摘要等） |
| `StockQuote` | 实时行情（最新价、涨跌幅、换手率等） |
| `FinancialMetric` 🆕 | 财务指标（ROE/毛利率/负债率/PE/营收增长率等） |
| `IndustryPosition` 🆕 | 产业链定位（上游/中游/下游 + 同行 + 主营构成） |
| `SupplyChainNode` 🆕 | 供应链节点（客户/供应商 + 交易占比） |

## 当前实现状态

| 特性 | 状态 | 测试数 |
|:-----|:----:|:------:|
| A股行情采集 | 已完成 | — |
| K 线数据采集 | 已完成 | — |
| 新闻采集 | 已完成 | — |
| 数据缓存（TTL） | 已完成 | — |
| Pydantic 标准化转换 | 已完成 | — |
| **C1 结构化简报分区输出** | 已完成 ✅ | 26（含5分区测试） |
| Provider 抽象层（4 源架构） | 已完成 ✅ | 84 |
| 多数据源接入（akshare/adata/zzshare/fallback） | 已完成 ✅ | — |
| **统一证据来源契约与注册中心** | **基础完成 ✅** | 11 |
| **CNINFO 权威公告适配器** | **直连三态门禁完成 ✅** | 18 |
| **DataEvidenceService 多通道统一汇总信封** | **完成 ✅** | 7 |
| **旧 Provider 六态适配** | **待接入 ⟳** | — |
| **基本面指标采集（FD-001）** | **待实现** ⟳ | — |
| **产业链定位（FD-001）** | **待实现** ⟳ | — |
| **供应链数据（FD-003 调研评估）** | **待调研** ⬜ | — |

## 下一步

### P0 基本面采集（FD-001）

1. `src/data/models.py` 新增 `FinancialMetric` / `IndustryPosition` / `SupplyChainNode`
2. `src/data/providers/base.py` DataSource Protocol 扩展
3. `src/data/providers/akshare.py` 实现 `get_financial_metrics()` + `get_industry_position()`
4. `src/data/collector.py` 新增采集方法 + `format_market_brief()` 填充基本面占位符

### 数据流

```
akshare.stock_financial_analysis_indicator(code)
  → AKShareSource.get_financial_metrics(code)
    → DataCollector.get_financial_metrics(code) [TTL=24h]
      → format_market_brief() → brief.sections["fundamentals"]
        → DebateState.market_data["financials"]
```

### 架构示意图（扩展后）

```
┌──────────────────────────────────────────────────────────────┐
│  DataCollector                                                 │
│  ├─ get_realtime_quotes()     → 行情（已有）                   │
│  ├─ get_kline()               → K 线（已有）                   │
│  ├─ get_news()                → 新闻（已有）                   │
│  ├─ get_financial_metrics() 🆕 → 财务指标（akshare 新接口）   │
│  └─ get_industry_position() 🆕 → 产业链定位（行业分类+主营）  │
├──────────────────────────────────────────────────────────────┤
│  所有方法委托 DataSource Protocol，4 Provider 实现             │
│  缓存 TTL：行情 30s / K 线 60s / 新闻 300s / 财务 24h         │
└──────────────────────────────────────────────────────────────┘
```

> **关联文档**：[RESEARCH.md](RESEARCH.md) — 调研背景
