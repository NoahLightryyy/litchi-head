---
department: 后端 API 部
codebase: backend/
last_updated: 2026-07-30 (K 线证据 KR-5 API 迁移计划批准)
---

# 🌐 后端 API 部工作交接

## 当前状态

### 模块完成度

| 子系统 | 状态 | 说明 |
|:-------|:----:|:------|
| market 路由（5 endpoint） | ✅ | 指数/板块排行/板块详情/brief/4 端点 |
| stocks 路由（5 endpoint） | ✅ | 搜索/行情/K 线/新闻/资金流向 |
| financials 路由（3 endpoint） | ✅ | 财务指标 /financials + 估值比率 /valuation + 动态指标 /indicators 🆕 |
| debate 路由（3 endpoint） | 🟡 | 功能可用；持久 session 原型已验证，但路由仍在内存、请求内同步执行 |
| trust 路由（2 endpoint） | ✅ | 信任度报告/排行榜 |
| 技术指标（indicators.py） | ✅ | MA/RSI/MACD/布林带纯 Python |
| 异步超时控制（async_utils.py） | ✅ | `run_sync()` 15s 超时封装 |
| 健康监控（/api/health） | ✅ | 实时数据源健康暴露 |
| evidence 路由（3 endpoint） | ✅ | 新闻、实时行情、L1 分时战况；逐源状态与完整性评估 |

### 测试

| 测试集 | 测试数 |
|:-------|:------:|
| test_market.py（6 端点 + 辅助函数 + hot-news） | 45 |
| test_stocks.py（8 端点 + financials/valuation/indicators） | 28 |
| test_debate.py（3 端点 + session 生命周期 + 限流） | 13 |
| test_trust.py（2 端点 + 映射逻辑） | 10 |
| test_retro.py（6 端点：records/summary/action/outcome/refresh/delete） | 26 |
| test_indicators.py（技术指标 100% 覆盖） | 43 |
| test_main.py + lifespan（health + 异常处理） | 9 |
| test_utils_backend.py（config 环境变量 + async_utils 超时） | 7 |
| test_evidence.py（新闻/行情/分时聚合、股票代码和时间范围校验） | 9 |
| **backend 合计（含 indicators）** | **190** |

### 关键架构决策

- **严格 HTTP 语义**：200 正常 / 404 无数据 / 422 验证失败 / 500 系统错误 / 503 数据源不可用
- **异步桥接**：所有同步数据采集调用通过 `run_sync(timeout=15)` 封装
- **CORS 环境变量化**：从 `BACKEND_CORS_ORIGINS` 读取，硬编码默认值仅用于开发
- **ADR-012 session 原型**：版本化信封 + SQLite WAL + 哈希恢复门禁；
  PostgreSQL 同信封重启恢复通过；真实 LLM 结果和最小 LangGraph 节点续跑已验证，
  尚未接入正式辩论图或路由

---

## 开放债务

| ID | 描述 | 优先级 | 预估 |
|:---|:-----|:------:|:----:|
| TD-054 | CORS 地址硬编码（需改环境变量） | 🟢 | 10min |
| TD-068 | 重型辩论无 durable queue、全局背压与恢复 | 🟡 | 2d |

## 已关闭

| ID | 标题 | 修复日期 |
|:---|:-----|:--------|
| TD-039 | debate/run API 速率限制 — slowapi 三层限流（run 6/min, status/result 30/min） | 2026-06-22 |
| TD-020 | 板块数据增强层缺失 | 2026-06-17 |
| TD-023 | 全返回 200 状态码 | 2026-06-17 |
| TD-024 | 数据源调用无超时 | 2026-06-17 |
| TD-036 | 路由测试全覆盖（176 tests） | 2026-07-27 |

---

## 下一步优先级

### 现有债务

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 ✅ | 新闻 `EvidenceEnvelope` 缺失返回 503；禁止不完整输入启动 LLM | 已完成 |
| 2 ✅ | 实时行情 `EvidenceEnvelope` 缺失/陈旧/冲突返回 503 | 已完成 |
| 3 🔥 | KR-5 扩展 K 线证据 API 与错误契约 | 2C 转换核心仍属数据部旁路；等待 TD-075/KR-3～4 后暴露统一信封，不直接暴露累计快照或未核验事件 |
| 4 🔥 | 将同一错误契约扩展到行业证据 | K 线完成后 |
| 2 🟡 | TD-068 正式辩论图 checkpoint + 路由 durable session 集成 | TD-069 |
| 3 🟡 | TD-068 1/3/5 并发、durable queue 与全局背压门禁 | 正式图恢复 |
| 4 🟢 | TD-054 CORS 改环境变量 | 无 |

### K 线证据 API 目标（2026-07-30 确认）

- 响应分别暴露 `final_daily_bars`、`final_minute_bars`、`live_quote` 和
  `provisional_session_bar`，不得把动态今日 OHLC 追加到完整日 K 数组；
- 每层携带 `as_of`、交易阶段、证据状态和逐源诊断；
- 正式日线指标与“含盘中估算”指标使用不同字段，禁止覆盖；
- 返回 `price_basis/adjustment_mode/reference_date/factor_version/upstream_ids`；
- RAW 冲突、复权冲突、独立上游不足使用不同稳定错误码；
- `POST /api/debate/run` 在开盘后使用上述分层输入，不等待收盘；
- 历史日 K 或盘中必需证据不完整时返回 HTTP 503，并给出缺失层、来源和重试建议。
- 旧 K 线展示接口先保持兼容，前端完成 KR-5 切换后再评估废弃。

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
| **FD-003b** 🥇 | **新增财务指标端点** — `GET /api/stocks/{code}/financials` + `GET /api/stocks/{code}/valuation` 返回财务指标+估值比率 JSON | 无 | ✅ 已完成 |
| **FD-003c** 🥇 | **新增产业链定位端点** — `GET /api/industry/{code}` 返回 `IndustryPosition` JSON | 数据管道部 FD-001d | ~1h |
| **FD-003d** 🥇 | **路由规范化** — 移除 `market.py` 中直接调 akshare 的代码（第114-138行），改为通过 `DataCollector` | 数据管道部 FD-001d | ~1h |
| **FD-003e** 🥈 | **板块详情页增强** — 新增财务摘要字段到 `/api/market/sector/{id}` 响应 | 数据管道部 FD-001d | ~1h |

### 🔴 必须修复的问题

| 问题 | 位置 | 描述 | 严重度 |
|:-----|:-----|:------|:------:|
| **伪产业链数据** | `market.py:187-228` | 按涨幅排序把成分股分为"上游/中游/下游"，不反映真实供应链关系，违反"零造假数据"政策 | 🔴 CRITICAL |
| **绕过 Provider 层** | `market.py:114-138` | 直接调 akshare，无缓存/健康监控，违反数据部规范 ROLE.md §禁止行为 | 🟡 HIGH |

### 产品定位新任务（PD 系列，2026-07-23 新增）

> **战略背景**：详见 [PRODUCT-POSITIONING.md](../../99-archive/PRODUCT-POSITIONING.md)。
> 核心方向：新增 2 个端点暴露行业定位 + 动态指标集，供前端展示"这个公司是什么位置、该看什么"。

| PD | 事项 | 状态 | 依赖 | 预估 |
|:--:|:-----|:----:|:----|:----:|
| **PD-008** 🥇 | **行业定位端点** — `GET /api/industry/{code}/position` 返回：产业链位置（上游/中游/下游）、判断理由（基于主营构成/行业分类）、该行业关键指标列表（名称+含义+当前值）| ⬜ **待办** | 数据部 PD-001~002 | ~1h |
| **PD-009** 🥇 | **动态指标端点** — `GET /api/industry/{code}/indicators` 返回：当前股票该看的 5-10 个指标（指标名+值+同行业分位+正常区间+一句话解读） | ✅ **已完成**（`/api/stocks/{code}/indicators`） | 数据部 PD-003 | ~1h |
| **PD-010** 🥇 | **FD-003a 伪产业链修复** — 同下方 FD-003a 任务，PD 系列重新编号以对齐产品定位，不再重复描述 | ⬜ **待办**（同 FD-003a） | 无 | 同 FD-003a |

### 新端点一览

```python
# ✅ 已完成 3 个端点（2026-07-24）
@router.get("/api/stocks/{code}/financials")
async def get_financials(code: str):
    """个股财务指标（ROE/毛利率/负债率等），含多报告期"""

@router.get("/api/stocks/{code}/valuation")
async def get_valuation(code: str):
    """个股估值比率（PE/PB/PS + 总市值）"""

@router.get("/api/stocks/{code}/indicators")  # 🆕 PD-009
async def get_indicators(code: str):
    """个股动态关键指标（按行业注册表筛选）"""

# 🆕 待办
@router.get("/api/industry/{code}", response_model=IndustryPositionResponse)
async def get_industry_position(code: str):
    """个股产业链定位（上游/中游/下游 + 同行 + 主营构成）"""

@router.get("/api/industry/{code}/position")  # 🆕 PD-008
async def get_industry_position_v2(code: str):
    """产业链位置 + 关键指标集 + 判断理由"""

@router.get("/api/industry/{code}/indicators")  # 🆕 PD-009
async def get_dynamic_indicators(code: str):
    """当前股票该看的 5-10 个指标 + 值 + 分位 + 解读"""

# 修复 1 个端点
@router.get("/api/market/sector/{id}") 
# 返回的 chain_map 用真实行业分类数据，移除伪产业链
```

---

## 决策 baseline / 影子验证责任（TD-074）

完整口径见 [跨部门唯一协议](../../02-requirements/DECISION_BASELINE_AND_SHADOW_VALIDATION.md)。
后端负责持久化实验任务、决策快照、结果回填和报告 API。当前请求内同步辩论与进程内
session 不能作为正式影子验证运行时；服务重启后任务、状态和审计引用必须可恢复。

## 关键文件索引

| 文件 | 说明 |
|:-----|:------|
| `backend/main.py` | FastAPI 应用入口 + CORS 配置 |
| `backend/routers/market.py` | 指数/板块/产业链路由 |
| `backend/routers/stocks.py` | 搜索/行情/K 线/新闻/资金流向路由 |
| `backend/routers/financials.py` | 🆕 财务指标/估值比率路由 |
| `backend/routers/debate.py` | 辩论触发/状态/结果路由 |
| `backend/routers/trust.py` | 信任度报告/排行榜路由 |
| `backend/indicators.py` | 纯 Python 技术指标计算 |
| `backend/async_utils.py` | 同步→异步超时桥接 |
| `backend/config.py` | 后端环境变量配置 |
| `tests/test_backend/` | 176 测试覆盖全部 19 端点 + 辅助函数 + 工具模块 |
| `docs/06-departments/08-backend-api/ROLE.md` | 👤 后端 API 部角色定义 |
| `docs/06-departments/08-backend-api/STANDARDS.md` | 📐 后端 API 部技术规范 |
