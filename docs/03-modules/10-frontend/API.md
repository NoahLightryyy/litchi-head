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
// 成功
{ "data": T, "meta": { "cached": boolean, "latency_ms": number } }

// 错误
{ "error": { "code": string, "message": string, "detail": any } }
```

## 接口索引

### 市场宏观

| 方法 | 路径 | 说明 |
|:----|:-----|:-----|
| GET | `/api/market/indices` | 三大指数行情 |
| GET | `/api/market/brief` | AI 宏观简报（LLM 生成） |
| GET | `/api/market/sectors` | 板块排行列表 |
| GET | `/api/market/sector/{id}` | 板块详情 + 产业链分析 |

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
  "meta": { "cached": true, "latency_ms": 125, "total": 86 }
}
```

### GET /api/market/sector/{id}

板块详情 + 产业链分析。

**响应**：
```typescript
{
  "data": {
    "sector": { /* 板块基础信息 */ },
    "chain_map": {
      "upstream": [   // 上游
        { "name": "锂矿/稀土", "key_companies": ["赣锋锂业", "天齐锂业"], "is_bottleneck": true }
      ],
      "midstream": [  // 中游
        { "name": "电池/电芯", "key_companies": ["宁德时代", "比亚迪"], "is_bottleneck": true }
      ],
      "downstream": [ // 下游
        { "name": "充电桩/储能", "key_companies": ["特锐德", "阳光电源"], "is_bottleneck": false }
      ]
    },
    "ai_analysis": {
      "summary": "锂电池为当前产业链核心瓶颈，宁德时代不可替代性最强...",
      "key_links": ["宁德时代", "赣锋锂业", "阳光电源"],
      "risk_factors": ["上游锂价波动", "海外政策风险"]
    },
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
