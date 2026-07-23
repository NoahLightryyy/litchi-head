---
department: 后端 API 部
codebase: backend/
last_updated: 2026-07-23 (FD 编号对齐)
---

# 🌐 后端 API 部工作交接

## 当前状态

### 模块完成度

| 子系统 | 状态 | 说明 |
|:-------|:----:|:------|
| market 路由（5 endpoint） | ✅ | 指数/板块排行/板块详情/brief/4 端点 |
| stocks 路由（5 endpoint） | ✅ | 搜索/行情/K 线/新闻/资金流向 |
| debate 路由（3 endpoint） | ✅ | 辩论触发/状态/结果 |
| trust 路由（2 endpoint） | ✅ | 信任度报告/排行榜 |
| 技术指标（indicators.py） | ✅ | MA/RSI/MACD/布林带纯 Python |
| 异步超时控制（async_utils.py） | ✅ | `run_sync()` 15s 超时封装 |
| 健康监控（/api/health） | ✅ | 实时数据源健康暴露 |

### 测试

| 测试集 | 测试数 |
|:-------|:------:|
| test_market.py（6 端点 + 5 辅助函数） | 52 |
| test_stocks.py（6 端点） | 15 |
| test_debate.py（3 端点 + session 生命周期） | 9 |
| test_trust.py（2 端点 + 映射逻辑） | 11 |
| test_indicators.py（技术指标 100% 覆盖） | 43 |
| **backend 合计** | **77** |

### 关键架构决策

- **严格 HTTP 语义**：200 正常 / 404 无数据 / 422 验证失败 / 500 系统错误 / 503 数据源不可用
- **异步桥接**：所有同步数据采集调用通过 `run_sync(timeout=15)` 封装
- **CORS 环境变量化**：从 `BACKEND_CORS_ORIGINS` 读取，硬编码默认值仅用于开发

---

## 开放债务

| ID | 描述 | 优先级 | 预估 |
|:---|:-----|:------:|:----:|
| TD-054 | CORS 地址硬编码（需改环境变量） | 🟢 | 10min |

## 已关闭

| ID | 标题 | 修复日期 |
|:---|:-----|:--------|
| TD-039 | debate/run API 速率限制 — slowapi 三层限流（run 6/min, status/result 30/min） | 2026-06-22 |
| TD-020 | 板块数据增强层缺失 | 2026-06-17 |
| TD-023 | 全返回 200 状态码 | 2026-06-17 |
| TD-024 | 数据源调用无超时 | 2026-06-17 |
| TD-036 | 路由测试全覆盖 | 2026-06-18 |

---

## 下一步优先级

### 现有债务

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 🟢 | TD-054 CORS 改环境变量 | 无 |

### 结果回调（RC 系列，2026-06-23 新增）

> 完整方案见 [ROADMAP.md RC 轨道](../../00-overview/ROADMAP.md#rc-结果回调轨道2026-06-23-新增--规划阶段)。

| RC | 事项 | 依赖 | 预估 |
|:--:|:-----|:----|:----:|
| **RC-003** 🥇 | **UB-TRACK 用户行为追踪 API** — 提供端点 `POST /api/user/action` 接收用户操作（buy/sell/hold/watch + 理由 + 分类），转发到 callback engine dispatch | 记忆系统部 RC-001 | ~1h |

### 用户经验反馈闭环（UI 系列，2026-06-23 新增 — 架构第9层）

> 完整方案见 [USER_FEEDBACK_LOOP.md](../../02-requirements/USER_FEEDBACK_LOOP.md)。
> 后端 API 部在闭环中负责：`POST /api/user/action` 端点 + RetroBoard API + 实际盈亏追踪。

| UI | 事项 | 依赖 | 预估 |
|:--:|:-----|:----|:----:|
| **UI-1b** 🥇 | **`POST /api/user/action` 端点** — 接收前端用户操作 → dispatch USER_ACTION_RECORDED | RC-001 + RC-003 模型 | ~1h |
| **UI-3a** 🥈 | **RetroBoard 后端 API** — `GET /api/retro/` 查询历史记录 + 聚合统计（准确率/胜率/最佳Agent） | UI-1 全部（数据积累） | ~2h |

### 基本面深度（FD 系列，2026-06-23 新增）

> **⚠️ 后端 API 部有一项数据造假债务必须立即修复**：`backend/routers/market.py:_build_chain_map()` 用涨幅排序虚构产业链上游/中游/下游，违反项目"零造假数据"红线。
>
> 完整背景见 [FUNDAMENTAL_RESEARCH.md](../../02-requirements/FUNDAMENTAL_RESEARCH.md)。

| FD | 事项 | 依赖 | 预估 |
|:--:|:-----|:----|:----:|
| **FD-003a** 🔴 | **修复伪产业链** — `_build_chain_map()` 改用真实行业分类（从 DataCollector.get_industry_position 获取），停止按照涨幅虚构上下游 | 无（可用现有 akshare 行业分类） | ~2h |
| **FD-003b** 🥇 | **新增财务指标端点** — `GET /api/financial/{code}` 返回 `list[FinancialMetric]` JSON | 数据管道部 FD-001d | ~1h |
| **FD-003c** 🥇 | **新增产业链定位端点** — `GET /api/industry/{code}` 返回 `IndustryPosition` JSON | 数据管道部 FD-001d | ~1h |
| **FD-003d** 🥇 | **路由规范化** — 移除 `market.py` 中直接调 akshare 的代码（第114-138行），改为通过 `DataCollector` | 数据管道部 FD-001d | ~1h |
| **FD-003e** 🥈 | **板块详情页增强** — 新增财务摘要字段到 `/api/market/sector/{id}` 响应 | 数据管道部 FD-001d | ~1h |

### 🔴 必须修复的问题

| 问题 | 位置 | 描述 | 严重度 |
|:-----|:-----|:------|:------:|
| **伪产业链数据** | `market.py:187-228` | 按涨幅排序把成分股分为"上游/中游/下游"，不反映真实供应链关系，违反"零造假数据"政策 | 🔴 CRITICAL |
| **绕过 Provider 层** | `market.py:114-138` | 直接调 akshare，无缓存/健康监控，违反数据部规范 ROLE.md §禁止行为 | 🟡 HIGH |

### 新端点一览

```python
# 新增 3 个端点
@router.get("/api/financial/{code}", response_model=FinancialMetricResponse)
async def get_financial_metrics(code: str):
    """个股财务指标（ROE/毛利率/负债率/估值等），含多报告期"""

@router.get("/api/industry/{code}", response_model=IndustryPositionResponse)
async def get_industry_position(code: str):
    """个股产业链定位（上游/中游/下游 + 同行 + 主营构成）"""

# 修复 1 个端点
@router.get("/api/market/sector/{id}") 
# 返回的 chain_map 用真实行业分类数据，移除伪产业链
```

---

## 关键文件索引

| 文件 | 说明 |
|:-----|:------|
| `backend/main.py` | FastAPI 应用入口 + CORS 配置 |
| `backend/routers/market.py` | 指数/板块/产业链路由 |
| `backend/routers/stocks.py` | 搜索/行情/K 线/新闻/资金流向路由 |
| `backend/routers/debate.py` | 辩论触发/状态/结果路由 |
| `backend/routers/trust.py` | 信任度报告/排行榜路由 |
| `backend/indicators.py` | 纯 Python 技术指标计算 |
| `backend/async_utils.py` | 同步→异步超时桥接 |
| `backend/config.py` | 后端环境变量配置 |
| `tests/test_backend/` | 77 测试覆盖 17 端点 |
| `docs/06-departments/08-backend-api/ROLE.md` | 👤 后端 API 部角色定义 |
| `docs/06-departments/08-backend-api/STANDARDS.md` | 📐 后端 API 部技术规范 |
