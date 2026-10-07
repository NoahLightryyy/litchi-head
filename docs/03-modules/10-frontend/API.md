# 前端 API 接口规范

> 前端通过 FastAPI 桥接层（`backend/`）调用后端 Python 逻辑。
> 所有接口返回 JSON，使用 Pydantic 序列化，兼容 OpenAPI 自动文档。

## 基础约定

```
Base URL: http://localhost:8000/api
Content-Type: application/json
```

**通用响应格式**：
```typescript
// 可消费响应（HTTP 200）
{ "data": T | null, "meta": {
  "status": "success" | "partial" | "empty" | "stale",
  "cached": boolean,
  "latency_ms": number,
  "missing_codes": string[],
  "failed_sources": string[],
  "limitations": { "code": string, "message": string, "index_code": string | null }[],
  "source_diagnostics": {
    "index_code": string, "source_id": string, "upstream_id": string,
    "status": "success_data" | "success_empty" | "failed" | "stale" | "conflicted",
    "latency_ms": number, "as_of": string | null,
    "error_code": string | null, "error_message": string | null
  }[],
  "sort_requested": string | null,
  "sort_applied": string | null
} }

// 市场数据不可用（HTTP 503）
{ "error": { "code": string, "message": string }, "meta": {
  "status": "failed", "cached": false, "latency_ms": number,
  "missing_codes": string[], "failed_sources": string[], "limitations": []
} }
```

市场首页四个接口使用上述稳定状态：`success` 表示要求的数据均可用；`partial` 表示仍有
可消费数据但存在明确缺口；`empty` 表示上游正常返回但没有可用业务数据；`stale` 表示
上游失败后返回了可用的过期缓存；`failed` 只出现在 503 错误信封。零值指数、空标题新闻
和无数据简报不得冒充成功。`partial/empty/stale` 是否重试由消费者按页面场景决定；503
可以重试，但不得自动改写为零值。

前端必须通过 `frontend/lib/market-contract.ts` 对网络响应做运行时校验，不能只依赖编译期
类型。`partial` 必须带缺失代码、失败来源或限制说明；`empty` 不得带可消费数据；
`stale` 必须设置 `cached=true`；指数 `price<=0`、新闻空标题及其他状态矛盾均视为契约
错误并进入错误态。已有数据后台刷新失败时可以保留，但必须常驻披露刷新失败。
指数项还必须校验带时区的 `as_of`、`source_count>=1` 和条目级 `cached`；`success` 的每项
必须至少双源且非缓存，`stale` 的每项必须明确为缓存。板块存在 `fund_flow=null` 时必须
同时披露 `FUND_FLOW_UNAVAILABLE`，且 `sort_applied` 不得为 `fund_flow`。板块详情同样通过
完整信封消费限制信息，不得只解包 `data` 后丢失事实边界。

## 接口索引

### 市场宏观

| 方法 | 路径 | 说明 |
|:----|:-----|:-----|
| GET | `/api/market/indices` | 三大指数行情 |
| GET | `/api/market/brief` | AI 宏观简报（LLM 生成） |
| GET | `/api/market/sectors` | 板块排行列表 |
| GET | `/api/market/hot-news` | 财新热点新闻；缺发布时间时返回 `partial` |
| GET | `/api/market/sector/{id}` | 板块详情；真实关系证据未接入时 `chain_map=[]` |

### 健康状态

| 方法 | 路径 | 说明 |
|:----|:-----|:-----|
| GET | `/api/health` | 后端进程与基础任务连通性 |
| GET | `/api/health/data-source` | 数据源调用次数、失败率、延迟与最近错误 |

前端必须分别判断“后端连通”和“数据源诊断”。诊断响应经运行时校验后再转换为
`healthy/degraded`；接口缺失或契约不兼容时只能显示诊断不可用，不能误报后端断开。
空业务结果由后端健康统计单独计为 `empty`，整体状态必须降级，不能计入成功率。

### 个股

| 方法 | 路径 | 说明 |
|:----|:-----|:-----|
| GET | `/api/stocks/search?q=` | 搜索股票/板块 |
| GET | `/api/stocks/{code}/quote` | 个股实时行情 |
| GET | `/api/stocks/{code}/kline` | K 线数据 |
| GET | `/api/stocks/{code}/news` | 个股新闻 |
| GET | `/api/stocks/{code}/capital-flow` | 资金流向 |

### 辩论决策

| 方法 | 路径 | 说明 |
|:----|:-----|:-----|
| POST | `/api/debate/run` | 触发辩论 |
| GET | `/api/debate/result/{session_id}` | 辩论结果 |
| GET | `/api/debate/status/{session_id}` | 辩论进度 |

### 统一证据

| 方法 | 路径 | 说明 |
|:----|:-----|:-----|
| POST | `/api/v1/evidence/news/aggregate` | 东方财富 + 新浪新闻证据信封 |
| POST | `/api/v1/evidence/quotes/aggregate` | 东方财富 + 新浪实时行情证据信封；含逐源状态与完整性 |
| POST | `/api/v1/evidence/intraday/battlefield` | 分钟价格曲线 + L1 战况；支持多源核验、单源可用、来源冲突与不可用四态 |
| 目标 | K 线双时间尺度证据信封 | `final_daily_bars`、实时/分钟与 `provisional_session_bar` 分栏；尚未实现 |

> `/api/stocks/{code}/quote` 是页面展示兼容接口；业务节点和 AI 辩论使用统一证据
> 接口。行情缺源、超过 10 秒、时间差超过 3 秒、价格差超过 0.01 元或不在连续
> 竞价时段（9:30–11:30、13:00–14:57）时，不启动 AI。行情聚合接口默认按 IP
> 限制为 6 次/分钟。
>
> 当日日 K 尚未收盘不是错误。盘中 AI 使用完整历史日 K、实时行情、已结束分钟和
> `PROVISIONAL` 今日动态状态；动态状态不得混入正式日 K 数组。
>
> K 线证据目标响应还必须包含 `price_basis`、`adjustment_mode`、`reference_date`、
> `factor_version`、`upstream_ids` 和字段精度，并区分 RAW 冲突、复权冲突与独立
> 上游不足。旧 K 线接口在 KR-5 迁移完成前保持兼容。

#### 分时战况前端契约

请求体为 `{ "symbol": "000001" }`。前端只使用响应中的真实字段：

- `price_points[].timestamp + close` 绘制分钟价格折线，不从单价点推造 OHLC；
- `verification_status` 区分 `multi_source_verified`、`single_source`、
  `source_conflict`、`unavailable`；单源和冲突只做持续可见提醒，不阻断可用数据；
- `source_diagnostics[]` 展示数据商名称、获取时间、检查点数量、状态和原始错误；
- `snapshot.session_vwap` 展示为 VWAP（成交量加权平均价），
  `relative_volume` 必须同时展示历史样本天数；
- `usable=false` 或价格点为空时不绘制示意曲线。网络错误与数据源不可用分开展示，
  网络错误不得猜测具体是哪家数据商失败。

前端每 30 秒轮询，查询在 15 秒后视为陈旧。已有可用数据刷新失败时保留最后一次可用画面，
常驻标红“刷新失败”和最后成功时间，避免短暂网络波动把图清空或把旧图冒充当前数据。
HTTP 边界对上述字段执行运行时契约校验；旧版后端若缺少单源放行字段，页面显示
“分时接口版本不兼容”，不得让 `undefined` 字段进入组件。

### 信任度

| 方法 | 路径 | 说明 |
|:----|:-----|:-----|
| GET | `/api/trust/report/{agent_name}` | 指定大师信任度 |
| GET | `/api/trust/leaderboard` | 大师信任度排行 |

## 接口详情

### GET /api/market/sectors

板块排行列表。当前行业/概念排行来源不提供主力资金流字段，因此不得宣称按资金流排序。

**响应**：
```typescript
{
  "data": [{
    "id": "BK0579",                    // 板块代码
    "name": "电力设备",                 // 板块名称
    "change_pct": 2.34,                // 涨跌幅 %
    "fund_flow": null,                 // 来源缺字段时必须为 null，不得用 0.0 冒充
    "heat": "high",                    // 热度（high/medium/low）
    "top_stocks": ["宁德时代", "阳光电源"], // 领涨个股
    "rank": 1,                         // 排名
  }],
  "meta": {
    "status": "success", "cached": false, "latency_ms": 125,
    "missing_codes": [], "failed_sources": [],
    "limitations": [{
      "code": "FUND_FLOW_UNAVAILABLE",
      "message": "当前板块排行来源未提供主力资金流字段，fund_flow 返回 null，不得按资金流解释或排序",
      "index_code": null
    }],
    "source_diagnostics": [],
    "sort_requested": "fund_flow",
    "sort_applied": "upstream_order"
  }
}
```

行业和概念来源之一失败但另一来源仍有数据时返回 HTTP 200 + `partial`，并在
`failed_sources` 标出失败来源；两者都失败且没有缓存时返回 HTTP 503 +
`MARKET_SECTORS_FAILED`。两者都正常但均为空时返回 HTTP 200 + `empty`。
2026-09-05 起，板块列表使用东方财富同源快照节点（仅首页展示，不增加独立来源数）。
每个 `SectorItem` 新增并始终序列化：

- `category: "industry" | "concept"`：来自已审计查询分类；
- `as_of: string | null`：上游板块时间；正式快照为带时区时间，null 只保留兼容测试边界；
- `source: "eastmoney"`；
- `snapshot_may_be_delayed: boolean`：正式快照恒为 true，消费者必须展示时间/延迟提醒。

正式快照以 `partial` 返回，并带 `BOARD_SNAPSHOT_MAY_BE_DELAYED`；行业总口径混合东财
一/二/三级，带 `BOARD_INDUSTRY_LEVELS_MIXED`，不得把496项宣传为同级行业。
官方目录 BK1362 无行情时带 `BOARD_CATALOG_QUOTE_MISSING`，不得补零。默认不加层级筛选，
`sort_requested/sort_applied` 及既有资金流/null语义不变。缓存命中由 `meta.cached=true` 表示，
条目 `as_of` 仍是原始上游时间，不改成缓存读取时间。

当任一返回条目缺少资金流字段时，条目 `fund_flow=null`、状态至少为 `partial`，限制码
`FUND_FLOW_UNAVAILABLE`；`sort_applied=upstream_order` 表示保持来源顺序，消费者必须据此
移除“按资金流排序”的表述。只有所有条目都有真实资金流且实际完成排序时，
`sort_applied=fund_flow`。

### 首页市场接口补充语义

- `/api/market/indices`：东方财富与新浪两路指数专用接口并发采集。每项返回 `as_of`、
  `source_count` 和 `cached`；双源价格差不超过 0.01 点且时间差不超过 3 秒时为完整数据，
  单源可用为 `partial + INDEX_SINGLE_SOURCE`。2026-09-04 用户批准：首页只要一个来源有效就展示；
  双源价时冲突也返回 HTTP 200 `partial`，选择时间最新的单源（同时间按 upstream_id 字典序最大值确定），
  `source_count=1`、`display_source` 标明所用 upstream，旁注 `INDEX_PRICE_CONFLICT` 或
  `INDEX_TIMESTAMP_CONFLICT`；不是双源共识。身份、价格或时间本身无效的源不能参与展示。
  全部无有效数据且失败时仍返回 `MARKET_INDICES_FAILED`；保留 `MARKET_INDICES_CONFLICTED`
  兼容错误码，但有效单源之间的价时冲突不再触发该码。最近 30 秒
  已核验缓存仅在双源失败时可作为 `stale` 返回；禁止构造 `0.00` 占位项。
- `/api/market/brief`：无可用指数时 `data=null`、状态 `empty`，不再返回“暂无数据”
  形式的成功简报。
- `/api/market/hot-news`：当前来源 `summary` 映射为 `title`；来源未提供发布时间时
  `date=null` 且状态 `partial`，限制码为 `PUBLISHED_AT_MISSING`。字段结构损坏或无缓存
  的上游失败返回 503；有旧缓存时返回 `stale`。

### GET /api/health/data-source

健康响应由 `DataSourceHealthResponse` 固定。每个 endpoint 只暴露计数、失败率、平均延迟、
最后成功距今秒数，以及安全的 `last_error`/`last_error_code`。新增必填
`current_status: healthy | failed | empty`；计数、失败率是进程生命周期历史，不能驱动当前告警。
`last_error` 是当前安全文案：请求失败“数据源请求失败”、冲突“来源数据冲突”、
空结果“数据源返回空数据”；成功清空 last_error/last_error_code，保留历史计数。不得
包含原始异常、URL、Token 或代理详情。指数来源分别以 `market_index:eastmoney` 和
`market_index:sina` 统计；同来源三指数整批原子发布，failed > empty > healthy，按批次
启动顺序防止旧批晚到覆盖新批。状态代表最后完成的批次，未完成请求不先清错；健康查询
不发上游请求、不自行重试、不改变进程健康 HTTP 状态。详情见
[健康恢复与展示集成说明](../../06-departments/08-backend-api/HEALTH-RECOVERY-INTEGRATION.md)。

### GET /api/market/sector/{id}

板块详情。`chain_map` 保留为兼容字段，但当前没有可核验产业链关系数据，因此返回空数组；
不得依据涨跌幅、价格或排行生成上下游关系。

**响应**：
```typescript
{
  "data": {
    "id": "BK001",
    "name": "银行",
    "chain_map": [],
    "ai_analysis": "基于成分股行情生成的市场表现摘要，不包含产业链关系推断。",
    "stocks": [
      { "code": "300750", "name": "宁德时代", "price": 256.80,
        "change_pct": 2.34, "fund_flow": null, "ai_rating": "A+" }
    ]
  }
}
```

板块详情沿用同一未知值纪律：板块或成分股资金流缺少已核验字段/单位时返回 `null`，
`meta.status=partial` 并携带 `FUND_FLOW_UNAVAILABLE`，不得使用 0.0 占位。

2026-09-06 起，详情的板块识别、板块行情和完整成分股分页均使用与列表相同的东方财富
快照适配器。板块与个股 `fund_flow` 均为亿元；`BOARD_SNAPSHOT_MAY_BE_DELAYED` 的
message 给出板块及成分股时间范围。`CHAIN_MAP_UNAVAILABLE` 仅标注关系数据缺失，不
阻止展示行情。价格或涨跌幅未知的成分股不以 0 补值，而是省略并标注
`MEMBER_QUOTE_UNAVAILABLE`。完整目录中不存在的 BK 代码返回 HTTP 404 +
`MARKET_SECTOR_NOT_FOUND`；若任一目录采集失败则返回 503，不能误判不存在。

### POST /api/debate/run

触发一次 AI 多 Agent 辩论。

**请求**：
```json
{
  "stock_code": "300750",
  "question": "当前是否适合买入宁德时代？",
  "enable_risk": true,
  "enable_trader": false,
  "enable_reflection": false
}
```

**响应**：
```json
{
  "data": {
    "session_id": "deb_20260616_abc123",
    "status": "running"
  }
}
```

### GET /api/debate/result/{session_id}

辩论完成后的结果。

**响应**：
```json
{
  "data": {
    "session_id": "deb_20260616_abc123",
    "stock_code": "300750",
    "stock_name": "宁德时代",
    "vote_summary": {
      "consensus": "看涨",
      "weighted_score": 72.5,
      "confidence": 0.82,
      "direction_distribution": { "Bullish": 3, "Bearish": 0, "Neutral": 1 },
      "trust_weight_factors": { "master.buffett": 1.2, "master.dalio": 1.5 }
    },
    "analyses": [
      { "agent_name": "master.buffett", "score": 72, "confidence": 0.85, "direction": "Bullish", "summary": "..." },
      { "agent_name": "master.dalio",   "score": 75, "confidence": 0.90, "direction": "Bullish", "summary": "..." }
    ],
    "total_latency_ms": 12450
  }
}
```

## 错误码

| Code | HTTP | 含义 | 前端处理 |
|:-----|:----:|:-----|:---------|
| `DATA_UNAVAILABLE` | 503 | 数据源不可用 | 显示缓存数据 + 提示 |
| `STOCK_NOT_FOUND` | 404 | 股票代码不存在 | 显示搜索建议 |
| `DEBATE_TIMEOUT` | 504 | 辩论超时 | 显示「请重试」按钮 |
| `LLM_ERROR` | 502 | AI 服务异常 | 显示「AI 暂时不可用」 |
| `RATE_LIMITED` | 429 | 请求太频繁 | 显示等待时间 |

## WebSocket

实时行情推送（待实现）：

```
ws://localhost:8000/ws/quotes?codes=000001,300750
→ { "code": "300750", "price": 256.80, "change_pct": 2.34, "timestamp": "2026-06-16T10:30:00Z" }
```

`BoardQuoteSnapshot.fund_flow` 保存东方财富 f62 原始元值；HTTP `SectorItem.fund_flow` 固定为亿元，
只在后端快照转响应时除以1e8。前端直接按亿元显示，不得再次除；任一条缺失均为null并触发
`FUND_FLOW_UNAVAILABLE`，`sort_applied=upstream_order`，不能按资金流排序。

2026-09-05：hot-news的date保留财新公开API原始time（Unix秒），以Asia/Shanghai的ISO8601字符串返回；非法/缺失保持null，不使用抓取时刻。API契约不变。

### 当日分时涨跌幅展示（2026-10-07）

沿用 `GET /stocks/{code}/quote` 已冻结的 `code`、`prev_close`、`fetched_at`（来源报价时间）与分时 `price_points.timestamp`。代码一致、昨收大于零且所有分钟点与报价为同一北京时间交易日时显示百分比轴。公式 `(价格/昨收-1)*100`；不以网页刷新时间或第一个分钟点作基准。未新增接口，不改变证据准入。五日图仍只展示价格轴。
