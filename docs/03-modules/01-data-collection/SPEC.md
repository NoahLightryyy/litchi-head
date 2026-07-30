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
| `src/data/news_store.py` | SQLite WAL 新闻元数据滚动存储、去重、保留期与连续覆盖 |
| `src/data/news_runtime.py` | 东方财富实时源 + 新浪滚动源的共享聚合运行时 |
| `src/data/intraday.py` | L1 分时模型、战况快照与确定性计算引擎 |
| `src/data/intraday_runtime.py` | 东方财富 + 腾讯分钟序列对账与失败关闭 |
| `src/data/models.py` | Pydantic 数据模型（StockInfo / KLine / NewsItem / StockQuote） |
| `src/data/cache.py` | 缓存层（带 TTL） |
| `src/data/providers/cninfo.py` | 巨潮资讯权威公告适配器（公开端点直连 + AKShare 可替换实现） |
| `src/data/providers/news.py` | 东方财富个股搜索 + 新浪财经快讯独立新闻适配器 |

## 架构（当前状态）

```
旧链路（仍在运行）：
DataCollector → DataSource → AKShare/AData/ZzShare/Fallback
                           └─ 失败仍可能被压成 [] / None

新契约（新闻双源已接入正式辩论）：
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

新浪后台采集（默认每 5 分钟）
  → 元数据写入 SQLite WAL（保留 3 天）
  → 采集间隔超过 10 分钟即重置连续覆盖起点
  → 满 3 天连续覆盖后才可作为成功上游
  → 与东方财富实时查询并发进入同一 EvidenceEnvelope
```

采集器必须确认已经读完整个当前可访问信息流；如果达到 20 页上限仍未耗尽，
本轮抛出截断错误且不得推进连续覆盖。乱序到达的旧采集批次可以补写条目，但不能
倒退 `last_success_at`。

### 多源完整性不变量

1. 同一个真实上游即使有多个适配器，也只算一个独立来源；
2. `SUCCESS_EMPTY` 只表示上游成功完成查询并明确返回零条；
3. 网络、解析和权限错误必须返回 `FAILED`，不能伪装成空数据；
4. RSSHub 等发现型来源标记为 `discovery_only`，不参与证据门槛；
5. 强制上游和独立来源数任一不足，评估结果均为 `complete=False`；
6. 汇总层只能传递统一证据模型、来源状态、时间范围和完整性结果，业务节点不依赖
   CNINFO、AKShare 等具体通道名称；
7. 新闻和实时行情契约已接管正式辩论图；任一不完整时图在首个 LLM 节点前结束并
   返回 `EVIDENCE_INCOMPLETE`。K 线和行业证据仍待迁移，因此 TD-069 暂不关闭。
8. 全局快讯没有覆盖完整请求时间窗时返回 `STALE`，不得用“当前页未命中”推断
   `SUCCESS_EMPTY`；
9. 跨源业务条目按股票与规范化标题去重，完整来源诊断仍保留在 `source_results`。
10. 新浪缓存只跨节点传输元数据，正文保持为空；首次部署或采集断档后必须重新积累
    连续 3 天覆盖，期间不得降级启动 AI。
11. 股票名称是新浪本地实体关联的必需输入；主数据无法解析名称时同样失败关闭，
    不能只用六位代码把可信空结果误判为完整核验。
12. 实时行情强制东方财富与新浪两个真实上游并发直连；东方财富成交量从“手”
    归一化为“股”。连续竞价（9:30–11:30、13:00–14:57）时数据年龄超过 10 秒即
    不可用于 AI，超过 30 秒记为硬过期；两源时间差不得超过 3 秒，价格差不得超过
    1 个最小价位（A 股 0.01 元）。
13. 午休、收盘和周末行情只允许展示，不允许启动新辩论；网络、解析、时间错位和
    价格冲突均保留逐源错误码，不能退回旧 Provider 静默降级。
14. 上海、深圳和北京市场代码必须统一识别；北交所旧 `4/8` 号段与新 `920`
    号段均使用新浪 `bj` 前缀。新浪响应变量中的真实证券代码必须与请求一致。
15. `DebateOrchestrator` 默认构造即启用行情门禁，只有测试或合成测量脚本可以
    显式传入 `quote_evidence_service=None`；聚合 API 默认每 IP 6 次/分钟。
16. L1 分时证据使用东方财富分钟 OHLC + 腾讯分钟收盘/累计量；成交量统一为股，
    已结束分钟集合、收盘价与累计量必须对账，当前动态分钟标为 `PROVISIONAL`。
17. 分时战况只输出 VWAP、开盘30分钟区间、同期相对量能等可观察事实；
    `attribution_supported=false`。没有 20 个交易日同分钟基线时 Relative Volume
    必须为不可用，禁止用上一分钟冒充历史基线。
18. 盘中 AI 的 K 线输入采用双时间尺度：上一交易日及以前的完整日 K 标记为
    `FINAL_DAILY`；已结束分钟标记为 `FINAL_MINUTE`；双源实时行情标记为
    `LIVE_QUOTE`；正在形成的今日 OHLC 标记为 `PROVISIONAL`。
19. `PROVISIONAL` 可以进入盘中 AI，但不得追加到完整日 K 数组，也不得用于生成
    “已确认日线形态”。收盘且多源确认后才能晋升为 `FINAL_DAILY`。
20. 正式日线指标只基于 `FINAL_DAILY`。含盘中估算的指标若提供，必须使用独立
    字段、明确标签和 `as_of`，不能覆盖正式值。

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
| K 线数据采集 | 旧链路已完成；双时间尺度证据门禁待实现 | — |
| 新闻采集 | 已完成 | — |
| 数据缓存（TTL） | 已完成 | — |
| Pydantic 标准化转换 | 已完成 | — |
| **C1 结构化简报分区输出** | 已完成 ✅ | 26（含5分区测试） |
| Provider 抽象层（4 源架构） | 已完成 ✅ | 84 |
| 多数据源接入（akshare/adata/zzshare/fallback） | 已完成 ✅ | — |
| **统一证据来源契约与注册中心** | **基础完成 ✅** | 11 |
| **CNINFO 权威公告适配器** | **直连三态门禁完成 ✅** | 18 |
| **DataEvidenceService 多通道统一汇总信封** | **完成 ✅** | 7 |
| **东方财富 + 新浪独立新闻证据源** | **完成 ✅** | 7 |
| **统一新闻聚合 API** | **完成 ✅** | 4 |
| **东方财富 + 新浪实时行情门禁** | **完成 ✅** | 21 |
| **统一实时行情聚合 API + 辩论失败关闭** | **完成 ✅** | 3+ |
| **东方财富 + 腾讯 L1 分时战况 API** | **一期完成 ✅** | 16 |
| **旧 Provider 六态适配** | **待接入 ⟳** | — |
| **基本面指标采集（FD-001）** | **待实现** ⟳ | — |
| **产业链定位（FD-001）** | **待实现** ⟳ | — |
| **供应链数据（FD-003 调研评估）** | **待调研** ⬜ | — |

## 下一步

### P0 K 线双时间尺度门禁（TD-069）

1. 多源核验已收盘日 K，并排除正在形成的当日条；
2. 汇总历史完整日 K、实时行情、已结束分钟和今日动态状态为分层信封；
3. 保持正式指标与盘中估算指标字段隔离；
4. 覆盖开盘可用、收盘晋升、来源冲突和零 LLM 失败关闭测试；
5. 完成后继续迁移行业证据。

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
