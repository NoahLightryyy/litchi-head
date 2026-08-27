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
  "limitations": { "code": string, "message": string }[]
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

板块排行列表，按资金流向排序。

**响应**：
```typescript
{
  "data": [{
    "id": "BK0579",                    // 板块代码
    "name": "电力设备",                 // 板块名称
    "change_pct": 2.34,                // 涨跌幅 %
    "fund_flow": 12.5,                 // 主力净流入（亿）
    "heat": "high",                    // 热度（high/medium/low）
    "top_stocks": ["宁德时代", "阳光电源"], // 领涨个股
    "rank": 1,                         // 排名
  }],
  "meta": {
    "status": "success", "cached": false, "latency_ms": 125,
    "missing_codes": [], "failed_sources": [], "limitations": []
  }
}
```

行业和概念来源之一失败但另一来源仍有数据时返回 HTTP 200 + `partial`，并在
`failed_sources` 标出失败来源；两者都失败且没有缓存时返回 HTTP 503 +
`MARKET_SECTORS_FAILED`。两者都正常但均为空时返回 HTTP 200 + `empty`。

### 首页市场接口补充语义

- `/api/market/indices`：仅返回价格大于零且真实匹配到的指数；缺少部分指数为
  `partial`，全部缺少为 `empty`，不再构造 `0.00` 占位项。
- `/api/market/brief`：无可用指数时 `data=null`、状态 `empty`，不再返回“暂无数据”
  形式的成功简报。
- `/api/market/hot-news`：当前来源 `summary` 映射为 `title`；来源未提供发布时间时
  `date=null` 且状态 `partial`，限制码为 `PUBLISHED_AT_MISSING`。字段结构损坏或无缓存
  的上游失败返回 503；有旧缓存时返回 `stale`。

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
        "change_pct": 2.34, "fund_flow": 2.1, "ai_rating": "A+" }
    ]
  }
}
```

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
