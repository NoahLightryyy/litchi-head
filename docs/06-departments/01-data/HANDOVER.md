---
department: 数据管道部
codebase: src/data/
last_updated: 2026-07-30 (KR-1B-2C-2C 北交所官方状态适配完成)
---

# 🗄️ 数据管道部工作交接

## 当前状态

### 模块完成度

| 子系统 | 状态 | 说明 |
|:-------|:----:|:------|
| 旧 Provider 抽象层（4 实现） | ✅ | AKShareSource / AData / ZzShareSource / FallbackSource |
| 多源证据契约 | ⟳ | 身份、真实上游、能力、六态结果、注册与完整性评估已完成；旧 Provider 待迁移 |
| CNINFO 公告证据源 | ✅ | 直连公开端点三态门禁；法定披露 PDF 停复牌事件保留附件哈希；AKShare 保留为可替换适配器 |
| DataEvidenceService | ✅ | 多通道并发采集、异常显式化、同 upstream 条目去重、统一 EvidenceEnvelope |
| 新闻双源证据 | ✅ | 东方财富个股搜索 + 新浪财经快讯；完整时间窗不足显式 STALE |
| 实时行情双源证据 | ✅ | 东方财富 + 新浪直连；时间、价格与交易阶段一致性门禁 |
| L1 分时战况 | ✅ 一期 | 东方财富 + 腾讯分钟对账；VWAP/开盘区间；当前条 `PROVISIONAL`；不做身份归因 |
| DataCollector 封装 | ✅ | 6 类数据，API 向后兼容 |
| 数据缓存（DataCache） | ✅ | 内存 TTL，各类型独立过期时间 |
| 数据模型（10 个 Pydantic） | ✅ | StockQuote / KLine / NewsItem / BoardInfo / CapitalFlowItem / FinancialMetrics / MarketBrief / BriefSection / ValuationMetrics |
| HealthStats 健康监控 | ✅ | 成功率/延迟/错误统计，/api/health 暴露 |
| 数据源审计 | ✅ | DATA_SOURCE_AUDIT.md 覆盖 10+ 平台 |

### 测试

| 测试集 | 测试数 | 覆盖率 |
|:-------|:------:|:------:|
| Provider 层单元测试 | 97 | 平均 83%（adata→83%, akshare→90%, fallback→100%） |
| 数据模型测试 | 31 | 100%（含 ValuationMetrics 9 测试） |
| 契约测试 data→debate | 4 | JSON roundtrip + format_market_brief |
| DataCollector 测试 | 81 | 含 get_valuation 8 测试 |
| 多源证据与汇总服务 | 47+ | 来源契约 + 汇总信封 + 新闻 + 实时行情 |

### 关键架构决策

- **四源架构**：akshare（主）→ adata（免费备）→ zzshare（兼容备）→ Fallback（自动切换）
- **零成本优先**：所有数据源免费，无 Tushare Pro 付费依赖
- **零造假数据**：全链路真实数据，无硬编码 mock
- **来源独立性按上游计算**：多个适配器包装同一媒体只算一个来源
- **失败不等于空数据**：新契约用六态结果显式区分成功空、失败、不支持、过期与冲突
- **扩展而不锁定**：业务层未来只依赖 `EvidenceSource`，新增付费源只增加适配器和配置

---

## 开放债务

| ID | 描述 | 优先级 | 预估 |
|:---|:-----|:------:|:----:|
| TD-034 | zzshare.py 死条件逻辑（两边值一样） | 🟢 | 5min |
| TD-057 | Provider 层测试（zzshare 46% 待补） | 🟡 | 30min |
| TD-064 | 财务指标覆盖率不足 | 🟢 | 1h |
| TD-072 | 20 日同分钟量能基线尚未积累 | 🟡 | 4h + 自然积累 |

---

## 下一步优先级

### R1 多源证据可靠性

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 ✅ | 东方财富 + 新浪免费新闻适配器 | 已完成 |
| 2 ✅ | 新闻完整性策略 + `/api/v1/evidence/news/aggregate` | 已完成 |
| 3 ✅ | 新闻信封在 LLM 前执行失败关闭 | 3 天双源门禁 + 零 LLM 已完成 |
| 4 ✅ | 实时行情迁移到统一门禁 | 双源直连 + 时效/配对/价差 + 零 LLM |
| 5 ✅ | L1 分时战况一期 | 东方财富 + 腾讯 + 统一业务信封 |
| 6 🔥 | 20 日同分钟量能基线 | TD-072 |
| 7 ✅ | K 线 KR-1A RAW 双源采集与严格对账 | 25 项契约 + 85% 专项覆盖 + 沪深北真实烟测 |
| 8 ✅ | K 线 KR-1B-1 官方市场日历与预期日期集 | 三市场 2026 版本；共同漏日/覆盖缺口失败关闭 |
| 9 ✅ | K 线 KR-1B-2A 官方证券状态契约 | 覆盖窗、上市退市、全天/盘中停牌、来源哈希 |
| 10 ✅ | K 线 KR-1B-2B 状态运行时门禁 | 全天停牌/生命周期过滤；覆盖不足失败 |
| 11 ✅ | K 线 KR-1B-2C-1 官方停复牌事件采集 | CNINFO 法定披露 PDF；明确日期、URL、SHA-256；300996 烟测 |
| 12 ✅ | K 线 KR-1B-2C-2A 连续状态账本 | 检查点、连续批次、重复归并、冲突/断档失败关闭 |
| 13 ✅ | K 线 KR-1B-2C-2B 沪深生命周期与检查点生成 | 交易所清单、CNINFO 批次哈希、确定性检查点、真实烟测 |
| 14 ✅ | K 线 KR-1B-2C-2C 北交所官方状态适配 | 上市清单/代码映射/市场日历；0600/0700、9001 分流；真实烟测 |
| 15 🔥 | K 线 KR-1B-3 长窗与持久化 | RAW/诊断/状态版本、覆盖证明与回放 |
| 15 🔥 | K 线 KR-2 统一复权 | RAW/公司行动/派生序列分层；点时因子 |
| 16 🔥 | K 线 KR-3 四层证据信封 | `FINAL_DAILY` 与今日 `PROVISIONAL` 严格分层 |
| 17 🔥 | 行业证据迁移到统一门禁 | K 线门禁完成后 |
| 4 🟡 | PostgreSQL 新闻去重、修订与来源关系持久化 | ADR-012 |
| 5 🟡 | 财联社版权和跨节点传输许可评估 | 用户确认后 |

### 现有债务

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 🟢 | TD-034 修 zzshare 死条件 | 无 |
| 2 🟢 | TD-057 补 zzshare 测试到 ≥80% | 无 |
| 3 🟢 | TD-064 审计遗漏财务指标 | 无 |

### 基本面深度 — 下放任务（⬜ 待办）

> 数据层 FD-001a~e 全部完成 ✅，辩论注入 FD-001f/g（辩论引擎部）也已完成。
> 以下为数据管道部剩余的 FD 待办，按优先级排列：

| 优先级 | 事项 | 预估 | 说明 |
|:------:|:-----|:----:|:------|
| 🥇 P0 | **FD-001h 多源财务数据** — ADataSource + ZzshareSource 实现 `get_financials()` | ✅ **已完成** | AData 用 `get_core_index`、Zzshare 用 `fina_indicator` |
| 🥇 P0 | **FD-002 估值比率模型** — PE/PB/PS 模型 + DataCollector.get_valuation() | ✅ **已完成** | 纯计算模型，8 测试 |
| 🥈 P1 | **FD-003 供应链数据调研** — 评估年报 PDF 解析可行性 | ~2h | 仅调研，非实现 |
| 🥈 P1 | **FD-004 财务指标覆盖率审计** — akshare 86 列审计遗漏关键指标 | ~1h | 当前仅取 17 列 |

### 基本面深度（FD 系列，2026-07-23 更新）

> 完整背景见 [FUNDAMENTAL_RESEARCH.md](../../02-requirements/FUNDAMENTAL_RESEARCH.md)。
> FD-001e~g 已完成：format_market_brief 填充真实财务数据、辩论注入、分析师增强（辩论引擎部协作）。

| FD | 事项 | 状态 | 依赖 | 预估 |
|:--:|:-----|:----:|:----|:----:|
| **FD-001a** 🥇 | **数据模型** — `FinancialMetrics`（17 指标：每股/盈利/增长/健康/运营/规模） | ✅ | 无 | ~1h |
| **FD-001b** 🥇 | **Provider 协议** — `DataSource.get_financials()` | ✅ | FD-001a | ~1h |
| **FD-001c** 🥇 | **AKShare 实现** — `stock_financial_analysis_indicator` → `FinancialMetrics` | ✅ | FD-001b | ~2h |
| **FD-001d** 🥇 | **Collector 方法** — `get_financials()` + TTL 1h 缓存 | ✅ | FD-001b | ~1h |
| **FD-001e** 🥇 | **填充基本面占位符** — `format_market_brief()` 已替换为真实财务数据，按6维度格式化输出 | ✅ | FD-001c | ~1h |
| **FD-001h** 🥇 | **多源财务数据** — ADataSource + ZzshareSource 实现 `get_financials()`（当前返回 `[]`） | ✅ **已完成** | FD-001c | ~1h |
| **FD-002** 🥇 | **估值比率模型** — PE(市盈率)/PB(市净率)/PS(市销率) 模型，Pure computation，纯计算不依赖 Provider | ✅ **已完成** | 股价+财务数据 | ~1h |
| **FD-003** 🥈 | **供应链数据调研** — 评估年报 PDF 解析前5大客户/供应商的可行性 | ⬜ **待办** | 无 | ~2h |
| **FD-004** 🥈 | **财务指标覆盖率审计** — akshare 86 列中当前只取了 17 列，审计遗漏关键指标 | ⬜ **待办** | FD-001c | ~1h |

### 用户经验反馈闭环（UI 系列，2026-06-23 新增）

> 完整方案见 [USER_FEEDBACK_LOOP.md](../../02-requirements/USER_FEEDBACK_LOOP.md)。
> 数据管道部在闭环中负责：UserBehaviorStore 存储层 + 实际盈亏追踪。

| UI | 事项 | 依赖 | 预估 |
|:--:|:-----|:----|:----:|
| **UI-1d** 🥇 | **UserBehaviorStore 存储层** — `data/user_profiles/` 目录 + JSONL 写入接口，按用户 ID 隔离（`src/callback/callbacks/ub_track.py` 中的 `UserBehaviorStore` 类归数据管道部维护）| RC-001 引擎 | ~1h |
| **UI-2b** 🥇 | **实际盈亏追踪** — 用户卖出时回填 `actual_outcome` / `actual_return_pct` / `holding_days`；定时扫描未了结交易计算浮动盈亏 | UI-1d | ~1h |

### 产品定位新任务（PD 系列，2026-07-23 新增 → 2026-07-24 全部完成 ✅）

> **战略背景**：详见 [PRODUCT-POSITIONING.md](../../99-archive/PRODUCT-POSITIONING.md)。
> 核心方向：动态指标选择（行业+产业链位置决定看哪 5-10 个指标），不和 Wind 比数据量。
> 配套任务：产业链位置判断 → 动态选指标 → AI 按行业上下文推理。
>
> **2026-07-24 实锤 API 验证**：
> - `ak.stock_board_industry_name_em()` → 496 个行业板块 ✅
> - `ak.stock_individual_info_em('000001')` → f127="银行Ⅱ" ✅
>
> 确认 API 返回二级行业名，需要归一化到一级行业（31 个，与申万一级对齐）。

| PD | 事项 | 状态 | 依赖 | 预估 |
|:--:|:-----|:----:|:----|:----:|
| **PD-001** 🥇 | **IndicatorRegistry 模型+注册表** — IndicatorDef Pydantic 模型 + 455 条行业归一化映射 + 31 个行业 × 5-8 个关键指标 + 18 个指标展开定义 | ✅ **已完成**（34 测试） | 无 | ~2h |
| **PD-002** 🥇 | **产业链位置判断** — 5 个上游/14 个中游/9 个下游/2 个金融/1 个综合 = 31 行业全覆盖 | ✅ **已完成** | PD-001 | ~1h |
| **PD-003** 🥇 | **动态采集引擎/选择器** — `DynamicIndicatorSelector.for_stock(code)` 全链路 + DataCollector 3 个公开方法 + TTL 1 天缓存 | ✅ **已完成** | PD-001, PD-002 | ~2h |
| **PD-004** 🥈 | **行业覆盖扩展** — 初始 31 个一级行业全覆盖（与申万一级对齐），455 条子板块归一化映射 | ✅ **一期已覆盖** | PD-001 | ~1h |
| **PD-005** 🥇 | **前端 FinancialPanel 行业感知** — 只显示注册表中该行业的关键指标，隐藏不相关字段 | ✅ **已完成** | PD-001~003 | ~1h |
| **PD-006** 🥇 | **行业定位 API 端点** — `/api/stocks/{code}/indicators` 返回动态指标 | ✅ **已完成** | PD-001~003 | ~1h |

**技术要点**：
- 455 条行业归一化映射覆盖东方财富全部 496 个子板块
- 使用静态 dict 而非数据库（编译时已知，启动时加载）
- 选择器全链路：stock_code → raw_industry → normalize → classify → REGISTRY → IndicatorDef
- 银行不显示毛利率/存货周转率 ✅

### 数据流变更

```
现有数据流（2026-07-23 更新）：

akshare.stock_financial_analysis_indicator(code)          ← 86 列季度财务数据
     ↓
AKShareSource.get_financials(code)                        ← Provider 协议 ✅
     ↓
DataCollector.get_financials(code)                        ← 缓存 TTL=1h ✅
     ↓
format_market_brief(financials=...)                       ← ✅ FD-001e
  → brief.sections["fundamentals"] = 6 维度格式化数据
     ↓
collect_data_node (辩论引擎部)                             ← ✅ FD-001f
  → market_data["brief"] 含财务数据 → 分析师自动消费

ADataSource.get_financials() (get_core_index) / ZzshareSource.get_financials() (fina_indicator)  ← ✅ FD-001h
ValuationMetrics (PE/PB/PS)  ← DataCollector.get_valuation()  ✅ FD-002（数据部 · 纯计算）
```

---

## 关键文件索引

| 文件 | 说明 |
|:-----|:------|
| `src/data/collector.py` | 统一数据采集入口（469 行） |
| `src/data/evidence.py` | 统一来源身份、能力、六态结果、注册与完整性评估 |
| `src/data/providers/cninfo.py` | CNINFO 权威公告统一证据适配器 |
| `src/data/providers/bse_status.py` | 北交所生命周期、代码映射与市场日历状态适配器 |
| `src/data/providers/news.py` | 东方财富 + 新浪独立新闻证据适配器 |
| `src/data/models.py` | 7 个 Pydantic 数据契约（140 行） |
| `src/data/cache.py` | 内存 TTL 缓存 |
| `src/data/providers/base.py` | DataSourceProtocol 抽象基类 |
| `src/data/providers/akshare.py` | AKShare 主数据源 |
| `src/data/providers/adata_source.py` | AData 免费数据源 |
| `src/data/providers/zzshare.py` | ZzShare 兼容数据源 |
| `src/data/providers/fallback.py` | 故障自动切换（已修复自动恢复） |
| `src/data/indicators/registry.py` | PD 动态指标体系 —— 模型+31行业注册表+455条归一化映射 |
| `src/data/indicators/selector.py` | PD 动态指标选择器 —— 全链路 for_stock(code) |
| `docs/06-departments/01-data/ROLE.md` | 👤 数据管道部角色定义 |
| `docs/06-departments/01-data/STANDARDS.md` | 📐 数据管道部技术规范 |

---

## 下次精确启动步骤

1. 先读 [ADR-013](../../05-decisions/ADR-013-multi-source-evidence.md) 与
   [实施计划 KR-1B](../../02-requirements/KLINE_EVIDENCE_IMPLEMENTATION_PLAN.md)；
2. KR-1A 已完成：`src/data/kline.py`、`providers/kline.py`、
   `kline_runtime.py` 与 25 项契约；不得重复实现或提前接入正式 AI；
3. 用户已确认免费官方方案，KR-1B-1 已实现；不得重复建立交易日历或改用聚合源；
4. KR-1B-2A/B/2C-1/2C-2A/2C-2B/2C-2C 已完成，不得重复状态契约、运行时
   门禁、沪深/CNINFO/北交所适配、连续状态归并、生命周期或检查点生成；
5. 北交所 0600/0700/9001、代码映射和生命周期边界已冻结；三家历史转板股的
   结构化上市日缺口登记 TD-073，不能用交易提示首日推断；
6. 下一步只做 KR-1B-3：证明长窗截断、RAW/诊断/状态版本持久化和回放；
7. KR-1B 真实烟测和故障注入通过后才进入 KR-2；不得同时提前改前端；
8. KR-2 通过后按 KR-3 输出 `FINAL_DAILY / FINAL_MINUTE / LIVE_QUOTE /
   PROVISIONAL`，再交给辩论、后端等下游；
9. 每个 KR 独立完成五同步和强制闸门，K 线全链路完成后再迁移行业证据。
