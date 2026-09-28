---
department: 后端 API 部
codebase: backend/
last_updated: 2026-09-06 (TD-081 详情真实恢复，待前端集成复验)
---

# 🌐 后端 API 部工作交接

> 跨部门优先级与上下游交付以[后端主管总工作表](../00-cross-cutting/BACKEND-SUPERVISOR-WORKLIST.md)为准。

## 当前状态

### 模块完成度

| 子系统 | 状态 | 说明 |
|:-------|:----:|:------|
| market 路由（6 endpoint） | ✅ | 双源指数、五态、nullable 资金流、逐源诊断已通过消费者与真实浏览器验收 |
| stocks 路由（5 endpoint） | ✅ | 搜索/行情/K 线/新闻/资金流向 |
| financials 路由（3 endpoint） | ✅ | 财务指标 /financials + 估值比率 /valuation + 动态指标 /indicators 🆕 |
| debate 路由（3 endpoint） | 🟡 | 功能可用；持久 session 原型已验证，但路由仍在内存、请求内同步执行 |
| trust 路由（2 endpoint） | ✅ | 信任度报告/排行榜 |
| 技术指标（indicators.py） | ✅ | MA/RSI/MACD/布林带纯 Python |
| 异步超时控制（async_utils.py） | ✅ | `run_sync()` 15s 超时；板块聚合共享截止并由 2 线程专用执行器限制取消后残留 |
| 健康监控（/api/health） | ✅ | 空结果触发 degraded；原始异常脱敏；指数逐源统计；浏览器无底层异常泄露 |
| evidence 路由（3 endpoint） | ✅ | 新闻、实时行情、L1 分时战况；逐源状态与完整性评估 |

### 测试

| 测试集 | 测试数 |
|:-------|:------:|
| test_market.py（6 端点 + 辅助函数 + hot-news） | 61 |
| test_stocks.py（8 端点 + financials/valuation/indicators） | 28 |
| test_debate.py（3 端点 + session 生命周期 + 限流） | 13 |
| test_trust.py（2 端点 + 映射逻辑） | 10 |
| test_retro.py（6 端点：records/summary/action/outcome/refresh/delete） | 26 |
| test_indicators.py（技术指标 100% 覆盖） | 43 |
| test_main.py + lifespan（health + 异常处理） | 12 |
| test_utils_backend.py（config 环境变量 + async_utils 超时） | 8 |
| test_evidence.py（新闻/行情/分时聚合、股票代码和时间范围校验） | 9 |
| **backend 合计（含 indicators）** | **210** |

### 关键架构决策

- **严格 HTTP 语义**：200 正常 / 404 无数据 / 422 验证失败 / 500 系统错误 / 503 数据源不可用
- **首页市场五态**：`success/partial/empty/stale` 返回 200；来源失败或字段损坏且无缓存
  返回 503 + `failed`。零值指数、空标题新闻和空简报不得进入成功信封
- **指数双源**：东方财富 + 新浪指数专用代码并发采集；0.01 点/3 秒一致性、单源降级、
  冲突失败关闭和 30 秒已核验缓存均结构化暴露
- **未知值与脱敏**：板块来源缺资金流时 `fund_flow=null`，健康响应不包含原始异常、URL
  或参数
- **异步桥接**：普通同步采集通过 `run_sync()` 封装（`DATA_TIMEOUT=15s`）；板块使用下述有界执行器
- **板块聚合调度**：行业/概念同时启动并共享 15 秒截止；详情以同一审计目录识别类型，
  再在同一总预算内完整分页拉取成分股。同步调用无法强杀，但专用 2 线程执行器限制重复超时的后台占用
- **板块详情失败契约**：聚合超时返回 HTTP 503 + `MARKET_SECTOR_DETAIL_TIMEOUT`；
  其他上游异常返回 HTTP 503 + `MARKET_SECTOR_DETAIL_FAILED`；两者均明确
  `retryable=true, retry_mode=client_controlled`；后端不重试，不改变前端既有重试策略
- **板块详情可用性**：BK1629/BK0475真实返回282/42只成分股；资金流为亿元；快照时间和
  可能延迟通过limitations披露。目录完整成功后仍无匹配才返回404，目录失败不能误报未找到
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
| TD-081 | 后端列表/详情修复完成，待集成分支浏览器联合验收 | 🟡 | 后端已完成 |
| TD-082 | 健康恢复与首页单源展示，待前端消费及联合验收 | 🟡 | 后端已完成 |

## 已关闭

| ID | 标题 | 修复日期 |
|:---|:-----|:--------|
| TD-039 | debate/run API 速率限制 — slowapi 三层限流（run 6/min, status/result 30/min） | 2026-06-22 |
| TD-020 | 板块数据增强层缺失 | 2026-06-17 |
| TD-023 | 全返回 200 状态码 | 2026-06-17 |
| TD-024 | 数据源调用无超时 | 2026-06-17 |
| TD-036 | 路由测试全覆盖（176 tests） | 2026-07-27 |
| TD-077 | 首页市场失败伪装成功；双源/五态/未知值/脱敏联合验收通过 | 2026-08-28 |

---

## 下一步优先级

### 现有债务

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 ✅ | 新闻缺源/陈旧时返回带限制结果；冲突/损坏时阻断 | 已完成 |
| 1 ✅ | 双源指数、五态、nullable 资金流与安全健康契约交给前端消费 | `5b4fc3a` → `87187ac`，前端 `40d7fcf` 与浏览器验收通过 |
| 2 ✅ | 实时行情缺源/陈旧时返回带限制结果；冲突/损坏时阻断 | 已完成 |
| 3 🔥 | KR-5 扩展 K 线证据 API 与错误契约 | KR-3B-2 失败契约已冻结但仍属数据部旁路；等待用户确认路线并完成 KR-4 后暴露统一信封，不直接暴露累计快照或未核验事件 |
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
- 研究推理使用不完整证据时返回完成结果并携带限制详情；冲突、身份错乱、未来数据等
  损坏证据才返回阻断错误。K 线证据 API 自身仍如实返回四层完整/失败信封。
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

> **✅ 2026-08-26 安全封口完成**：`backend/routers/market.py:_build_chain_map()` 已停止用
> 涨幅排序制造产业链。现有行情字段不能证明上下游关系，因此在真实关系数据源和契约
> 获批前稳定返回 `chain_map=[]`。
>
> 完整背景见 [FUNDAMENTAL_RESEARCH.md](../../02-requirements/FUNDAMENTAL_RESEARCH.md)。

| FD | 事项 | 依赖 | 预估 |
|:--:|:-----|:----|:----:|
| **FD-003a** ✅ | **伪产业链安全封口** — `_build_chain_map()` 不再依据行情排名制造关系；无证据返回空列表 | 真实产业链能力仍需批准数据源与契约 | ✅ 已完成 |
| **FD-003b** 🥇 | **新增财务指标端点** — `GET /api/stocks/{code}/financials` + `GET /api/stocks/{code}/valuation` 返回财务指标+估值比率 JSON | 无 | ✅ 已完成 |
| **FD-003c** 🥇 | **新增产业链定位端点** — `GET /api/industry/{code}` 返回 `IndustryPosition` JSON | 数据管道部 FD-001d | ~1h |
| **FD-003d** 🥇 | **路由规范化** — 移除 `market.py` 中直接调 akshare 的代码（第114-138行），改为通过 `DataCollector` | 数据管道部 FD-001d | ~1h |
| **FD-003e** 🥈 | **板块详情页增强** — 新增财务摘要字段到 `/api/market/sector/{id}` 响应 | 数据管道部 FD-001d | ~1h |

### 🔴 必须修复的问题

| 问题 | 位置 | 描述 | 严重度 |
|:-----|:-----|:------|:------:|
| **真实产业链能力待建** | `market.py:_build_chain_map()` | 伪造算法已移除；当前稳定返回空列表，真实上下游关系仍缺已批准数据源 | 🟡 待决策 |
| **绕过 Provider 层** | `market.py:114-138` | 直接调 akshare，无缓存/健康监控，违反数据部规范 ROLE.md §禁止行为 | 🟡 HIGH |

### 产品定位新任务（PD 系列，2026-07-23 新增）

> **战略背景**：详见 [PRODUCT-POSITIONING.md](../../99-archive/PRODUCT-POSITIONING.md)。
> 核心方向：新增 2 个端点暴露行业定位 + 动态指标集，供前端展示"这个公司是什么位置、该看什么"。

| PD | 事项 | 状态 | 依赖 | 预估 |
|:--:|:-----|:----:|:----|:----:|
| **PD-008** 🥇 | **行业定位端点** — `GET /api/industry/{code}/position` 返回：产业链位置（上游/中游/下游）、判断理由（基于主营构成/行业分类）、该行业关键指标列表（名称+含义+当前值）| ⬜ **待办** | 数据部 PD-001~002 | ~1h |
| **PD-009** 🥇 | **动态指标端点** — `GET /api/industry/{code}/indicators` 返回：当前股票该看的 5-10 个指标（指标名+值+同行业分位+正常区间+一句话解读） | ✅ **已完成**（`/api/stocks/{code}/indicators`） | 数据部 PD-003 | ~1h |
| **PD-010** 🥇 | **FD-003a 伪产业链修复** — 后端安全封口完成；真实关系能力另行决策 | ✅ **安全封口完成** | 新数据源与字段契约待确认 | — |

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
# 真实关系数据接入前 chain_map=[]，禁止从行情字段推断产业链
```

---

## 2026-08-26 协调会任务下发

**主责指标**：API-1 契约交付、TRACE-1 追溯与恢复。

| 任务要求 | 部门验收口径 |
|:---------|:-------------|
| 暴露四层成功信封 | `final_daily_bars`、`final_minute_bars`、`live_quote`、`provisional_session_bar` 不混装 |
| 暴露稳定失败契约 | 错误响应包含稳定码、缺失层、逐源诊断、`as_of` 和重试建议；HTTP 状态有契约测试 |
| 保持兼容迁移 | 旧 K 线接口在前端切换前保持兼容；退役必须有引用清理和单独确认 |
| 持久化长任务与审计引用 | 重启后任务状态、结果、失败和证据引用可恢复，不依赖进程内字典 |

**依赖闸门**：KR-3B-2 已冻结，KR-4 尚待用户转段确认；字段、HTTP 映射和用户可见错误语义须与前端共同
评审并由用户确认。

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

## 前端总清单分工（FW）

> 总状态见[前端总工作清单](../../03-modules/10-frontend/WORKLIST.md)。

| 协调项 | 本部门细分责任 | 验收证据 |
|:-------|:---------------|:---------|
| FW-012 | 每次 AI 请求返回稳定任务身份、当前状态、证据引用和失败事实；恢复后不串会话 | 新请求失败时不会返回旧成功 payload；任务可持久恢复 |
| FW-020 | 提供四层证据 schema、稳定错误响应、HTTP 映射、重试语义和兼容迁移 | 契约测试覆盖成功/失败；旧接口仅在前端迁移完成后退役 |
| FW-022/023 | 提供晋升、健康、超时、限流和恢复所需的可观察接口事实 | 重试幂等；健康接口不把业务失败包装成健康 |
| FW-030 | 输出稳定 OpenAPI/schema 供 TypeScript 生成并在 CI 检查漂移 | 生成结果可重复；破坏性变化明确失败 |
| FW-040/050/060 | 提供真实产业链/比较、用户操作和效果证据接口 | 不新增未经确认字段、风险默认值或用户文案 |

## 2026-09-04 首页健康恢复交付

TD-082 后端已完成批次健康恢复和首页有效单源展示；来源验证在旁注，正式决策门禁不变。
TD-081 上游仍失败，独立端口板块 14.58s/503；指数三项新浪单源 200。
前端消费、SHA 集成路径、上游限制见[集成说明](../08-backend-api/HEALTH-RECOVERY-INTEGRATION.md)。
待前端联合验收后关闭债务，未修改现有预览。

### 板块第二轮候选

同源快照适配器已完成并实测496行业/504概念，支持完整分页、8秒总预算和30秒缓存。
用户确认继续后已正式接入首页列表；冷0.282s、热0.047s返回1000项。见集成说明第三轮，待前端联合验收。
前端父任务已将重复57号并发学习卡移至58号，本分支本轮不新增编号卡片。

## 2026-09-05 热点快讯原始发布时间恢复

原财新API包含Unix秒time，AKShare stock_news_main_cx投影仅保留tag/summary/url，丢弃时间。新增caixin_news适配同一公开端点，保留既有摘要顺序与链接，将time转为带+08:00的ISO时间；不改变HTTP date:string|null契约。缺失/非法时间仍null并保留既有partial限制，网络失败走现有日志、stale缓存及503路径。

真实接口200、30/30条有date、status=success且limitations为空，约0.519秒。首条2026-09-05T08:52:19+08:00。浏览器真实DOM确认30条时间与缺失告警消失。check.py Ruff/Pyright/后端数据模块测试3/3通过；新增9个适配器用例与1个HTTP贯通用例。8000重启为当前分支PID31460，3000无需改动。原AKShare调用与测试patch已替换，旧日志只留历史事实。


## FW-041 用户下发：产业投资研究全景重构（2026-09-08）

总状态及完整需求见[FW-041唯一总表](../../03-modules/10-frontend/WORKLIST.md#fw-041-产业投资研究全景重构2026-09-08-用户下发)。本部门任务已登记，未启动实现。

- 本部门责任：冻结研究响应与节点/公司/证据查询契约。
- 交付与验收：Pydantic/OpenAPI、错误/状态/重试/兼容、部分缺失和更新时间明确；提交后交前端。
- 上游依赖：数据/Agent/风控方案。
- 交接纪律：研究方案先于接口，后端契约冻结提交先于前端；不得将历史行业分类图标为当前瓶颈研究完成。既有来源授权沿用，新增资金默认值/超范围来源另行审定。

FW-041补充：多维个股研究应分别覆盖盈利质量、估值、成长、财务风险、产业位置与行情，说明指标标准、时间和缺项；不得按涨幅冒充AI评级。当前前端仅先取消旧字母并添加行情分类分页。详见FW-041总表的多维个股研究补充。

FW-041入口细化：用户明确多维研究需前置到板块选股区，不能只放个股详情。本部门任务：契约须覆盖板块公司批量多维数据、筛选排序/分页与公司对比所需能力；共享个股证据，避免逐只串行加载拖慢选股。 具体验收与唯一状态见前端WORKLIST中的“FW-041 板块页多维选股区”。已登记，尚未实现。

## FW-070 导航整合任务（2026-09-09）

用户批准六主入口和底部数据状态/设置，已登记待办，尚未实现。本部门责任：盘点六入口及底部健康/设置可复用接口，新增契约先冻结；选股与板块筛选共享服务。 上游依赖、完整范围及验收以[FW-070总表](../../03-modules/10-frontend/WORKLIST.md#fw-070-导航与投资工作流程整合2026-09-09-已批准)为准。先盘点能力，再按契约和页面就绪程度分阶段交付。

### 2026-09-09 FW-070 基础工作区交付

六入口及数据状态/设置已接通；股票/基金手动持仓方案已获用户授权。本轮仅本机存储和既有API消费，无新后端契约、账户接入或交易。状态及验收统一回链[FW-070](../../03-modules/10-frontend/WORKLIST.md)。完整当期产业研究、多维筛选和自动跟踪尚未完成，不能以菜单齐全关闭这些依赖。

2026-09-09 个股修复：300913旧分时信封缺少前端要求字段，已补齐可展示单源价格点与来源诊断，真实页面恢复267点；complete仍要求双源。K线日期参数与空缓存已修，实网东方财富ProxyError仍未解决，TD-069相关源可用性保持开放。见[验收日志](../../04-changelog/logs/2026-09-09/2026-09-09-stock-recovery.md)。

2026-09-20后续：用户已批准腾讯不复权备用，独立kline-raw-display契约与日线降级展示已实现；先前“待确认”已解除。仅原日线空/失败时使用，展示来源、日期、不复权与单源限制；不代表TD-069研究证据、周/月线及全页数据故障关闭。

## 2026-09-28 BK0596恢复进度

成分股改为稳定代码排序、最多8路并发完整分页。真实3874条/3.96秒；34项Provider测试及check.py三道闸门通过（776 passed / 4 skipped）。
API字段、错误码、前端文案均未改。端到端验收未通过：行业/概念目录502，使详情HTTP503，浏览器仍显示失败。TD-081重开，不能标为整个板块已恢复。
8000后端与3001生产前端已在隔离worktree启动。
