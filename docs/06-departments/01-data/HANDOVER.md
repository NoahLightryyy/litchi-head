---
department: 数据管道部
codebase: src/data/
last_updated: 2026-08-27 (首页指数双源汇总与健康脱敏)
---

# 🗄️ 数据管道部工作交接

> 跨部门优先级与上下游交付以[后端主管总工作表](../00-cross-cutting/BACKEND-SUPERVISOR-WORKLIST.md)为准。

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
| 首页指数双源证据 | 🧪 | 东方财富 + 新浪指数专用代码；并发、0.01 点/3 秒核验、单源降级、冲突关闭、30 秒缓存 |
| L1 分时战况 | ✅ 二期底座 | 双源分钟对账；腾讯历史影子回填；正式20日基线只读双源完整日 |
| DataCollector 封装 | ✅ | 6 类数据，API 向后兼容 |
| 数据缓存（DataCache） | ✅ | 内存 TTL，各类型独立过期时间 |
| 数据模型（10 个 Pydantic） | ✅ | StockQuote / KLine / NewsItem / BoardInfo / CapitalFlowItem / FinancialMetrics / MarketBrief / BriefSection / ValuationMetrics |
| HealthStats 健康监控 | 🧪 | 逐源成功/空/失败/延迟；API 仅暴露安全错误码和固定文案，原始异常只进日志 |
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
| TD-072 | 20 日同分钟量能基线暖机与影子验证 | 🟡 | 代码完成 + 自然积累 |

---

## 下一步优先级

### R1 多源证据可靠性

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 ✅ | 东方财富 + 新浪免费新闻适配器 | 已完成 |
| 2 ✅ | 新闻完整性策略 + `/api/v1/evidence/news/aggregate` | 已完成 |
| 3 ✅ | 新闻信封进入限制披露/损坏阻断 | 3 天双源；缺源带标注推理，冲突/损坏零 LLM |
| 4 ✅ | 实时报价迁移到统一证据分类 | 双源直连；缺源/陈旧带标注推理，冲突/错时零 LLM |
| 5 ✅ | L1 分时战况一期 | 东方财富 + 腾讯 + 统一业务信封 |
| 6 🧪 | 20 日同分钟量能基线 | TD-072 代码完成；等待20个双源日与影子验证 |
| 7 ✅ | K 线 KR-1A RAW 双源采集与严格对账 | 25 项契约 + 85% 专项覆盖 + 沪深北真实烟测 |
| 8 ✅ | K 线 KR-1B-1 官方市场日历与预期日期集 | 三市场 2026 版本；共同漏日/覆盖缺口失败关闭 |
| 9 ✅ | K 线 KR-1B-2A 官方证券状态契约 | 覆盖窗、上市退市、全天/盘中停牌、来源哈希 |
| 10 ✅ | K 线 KR-1B-2B 状态运行时门禁 | 全天停牌/生命周期过滤；覆盖不足失败 |
| 11 ✅ | K 线 KR-1B-2C-1 官方停复牌事件采集 | CNINFO 法定披露 PDF；明确日期、URL、SHA-256；300996 烟测 |
| 12 ✅ | K 线 KR-1B-2C-2A 连续状态账本 | 检查点、连续批次、重复归并、冲突/断档失败关闭 |
| 13 ✅ | K 线 KR-1B-2C-2B 沪深生命周期与检查点生成 | 交易所清单、CNINFO 批次哈希、确定性检查点、真实烟测 |
| 14 ✅ | K 线 KR-1B-2C-2C 北交所官方状态适配 | 上市清单/代码映射/市场日历；0600/0700、9001 分流；真实烟测 |
| 15 ✅ | K 线 KR-1B-3A 审计持久化 | SQLite 不可变清单 + 内容寻址 Parquet；RAW/诊断/权威版本引用与 `as_of` 回放 |
| 16 ✅ | K 线 KR-1B-3B 长窗覆盖 | 腾讯连续分段与准确响应证明；新浪不可证明请求起点时保留部分 RAW 并失败关闭；审计运行时已持久化 |
| 17 ✅ | K 线 KR-2 统一复权 | 沪深普通/差异化/修订链、点时因子与故障关闭均完成 |
| 18 ✅ | K 线 KR-3 四层证据信封 | KR-3A、KR-3B-1、KR-3B-2 全部完成；等待用户转段确认 |
| 19 🔥 | 行业证据迁移到统一门禁 | K 线门禁完成后 |
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

## 2026-08-26 协调会任务下发

**主责指标**：EVI-1 证据完整性、TRACE-1 追溯与恢复。

| 任务要求 | 部门验收口径 |
|:---------|:-------------|
| ✅ KR-3B-2 把 KLINE/INTRADAY/REALTIME_QUOTE 三类运行时失败归并到四层诊断 | 每个失败请求只返回 `KlineBusinessFailure`，缺失层、逐源诊断和稳定错误码齐全；已完成 |
| 保持成功与失败边界不可混淆 | 任何不完整残留、未知异常、跨证券或跨快照输入不得生成成功信封 |
| 保持确定性与审计血缘 | 相同冻结输入产生相同失败结果；保留 `as_of`、快照、因子和上游引用 |
| 不改变已批准数据纪律 | 不新增数据源，不复用实时/分钟/完成日线阈值，不让事件或累计快照单独进入下游 |

**依赖闸门**：错误码集合、归并顺序和重试语义已获用户确认并冻结；后续工作按后端
主管总表的转段闸门执行，路线确认前只允许 RED 契约和影响分析，不接入辩论、API 或前端。

## 决策 baseline / 影子验证责任（TD-074）

完整口径见 [跨部门唯一协议](../../02-requirements/DECISION_BASELINE_AND_SHADOW_VALIDATION.md)。
数据部在 KR-2～6 后负责点时行情、公司行动、统一复权、基准数据和到期结果标签。
AI 与 baseline 必须使用同一时点、价格坐标和成本口径；失败、停牌、拒答和缺口均保留。
未经用户确认，不得为了补 baseline 擅自增加数据源。

## KR-2 统一复权完成状态（2026-08-04）

- ✅ KR-2A 已完成：RAW 与派生序列类型隔离；因子版本/修订/双路血缘；
  `raw_snapshot_id + raw_completed_through + as_of` 点时证明；现金、送转、拆并股、
  配股跨停牌和修订回放；26 项合成契约；
- ✅ KR-2B-1 已完成：方案 A 的沪深新浪累计 QFQ 除数直连、原始字节哈希、
  Decimal 精度/哨兵/锚点/顺序校验、网络与脏数据错误分流、沪深真实烟测；
- ⛔ 北交所在独立官方公司行动核验源完成前于触网前返回不支持；
- ✅ KR-2B-2A 已完成：官方文档/事件冻结契约、严格金额/精确比例、点时采集边界、
  解析器版本、六类条款矩阵及契约测试；
- ✅ KR-2B-2B1 已完成：深市标准权益分派正文、含税现金/送转、最终日期章节、
  同日聚合、分页漂移与真实 `000001` 样本；
- ✅ 2B2A：SSE 普通/差异化、配股最终日程、双现金口径与修订账本契约；
- ✅ 2B2B：更正/延期/终止等公告唯一归链，缺原公告时同源回填 365 天；歧义、
  倒序或缺更正后完整正文失败关闭；
- ✅ 2C 转换核心：相邻累计除数、官方事件与登记日 RAW 严格匹配；现金、送转、
  配股和组合公式复算；因子/核验双路血缘、修订版本和较晚采集时间完整保留；
- ✅ 用户批准新浪 16 位尾差按 12 位 `ROUND_HALF_EVEN` 校验，输出精度至少
  `1e-12`；12 位可见冲突继续失败关闭；
- ✅ 深市 `000001` 2025-06、2025-10、2026-06 三次真实现金分派全链通过；
- ✅ TD-075 关闭：SSE 重要提示/正文相同日期表按值幂等归并，不同日期仍冲突；
  支持“（修订版）”完整正文及完整标题空白归一，解析器升至 v4；
- ✅ 沪市 `600000` 普通、`688008` 差异化、`688503` revision 3 真实修订链均从
  CNINFO、Sina、Tencent RAW 全链生成已核验因子；三上游超时故障注入失败关闭；
- ✅ KR-2 整体完成；KR-3A 四层契约与晋升核心也已完成。
- ✅ KR-3A 完成：四层成功信封、四层诊断失败结果、深度冻结行情事实与幂等收盘
  晋升核心；51 项契约通过。
- ✅ KR-3B-1 完成：三类完整运行时证据组装、能力/证券接线校验、残留半成品拒绝和
  `FINAL` 分钟隔离；复权序列必须匹配持久化 RAW 快照，canonical 实时报价必须
  恰好一条；14 项新契约通过。
- ✅ KR-3B-2 完成：三类失败确定性映射四层；报价失败同步关闭 LIVE/PROVISIONAL；
  逐源诊断不携带行情，主错误排序稳定，三档重试处置冻结；complete 信封中的身份、
  会话和时间边界损坏同样失败关闭；数据部 696 项回归通过。
  当前等待用户转段确认，确认前仍不得切入 AI/API。

## 关键文件索引

| 文件 | 说明 |
|:-----|:------|
| `src/data/collector.py` | 统一数据采集入口（469 行） |
| `src/data/evidence.py` | 统一来源身份、能力、六态结果、注册与完整性评估 |
| `src/data/kline_adjustment.py` | KR-2A 版本化因子/点时 QFQ、官方事件契约，以及 KR-2B-2C 已核验因子转换 |
| `src/data/kline_business.py` | KR-3A 四层成功/失败业务契约、深度冻结事实与幂等收盘晋升 |
| `src/data/kline_business_runtime.py` | KR-3B 成功/失败结果组装、RAW 快照血缘、四层诊断归并和重试处置 |
| `src/data/providers/sina_adjustment.py` | KR-2B-1 新浪累计 QFQ 除数证据快照；不生成公司行动事件因子 |
| `src/data/providers/cninfo_actions.py` | KR-2B-2B1～2B2B 沪深模板、配股、差异化双口径、修订唯一归链与历史回填 |
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
6. KR-1B-3A/3B 已完成，统一复用 `src/data/kline_store.py` 与
   `RawDailyKlineEvidenceRuntime.collect_and_persist()`；不得另建 K 线清单、
   Parquet 目录、逻辑快照哈希或 `as_of` 回放；
7. 腾讯长窗必须按不超过 1000 日连续分段；新浪最早原始日期未覆盖请求起点时
   固定失败关闭并保留部分 RAW。完整快照必须带日历权威，且每个成功源独立覆盖
   全部 canonical 日期并通过同日对账；
8. KR-2A 已完成，不得重复实现：冻结因子契约、精确股本比例/因子精度校验、
   完整血缘内容哈希、`raw_snapshot_id + raw_completed_through` 点时边界、
   Decimal 确定性与 26 项合成契约均在 `src/data/kline_adjustment.py`；
9. 方案 A 已确认且 KR-2B-1 已完成，不得重复实现：沪深新浪累计除数直连、
   内容寻址快照、错误分类和 BSE 失败关闭均在 `sina_adjustment.py`；
10. KR-2B-2A 已完成，不得重复模型：官方文档、事件、现金/股本/配股条款和点时
   采集边界均在 `kline_adjustment.py`；
11. KR-2B-2B1 已完成，不得重复深市标准模板、分页/PDF/hash 或同日聚合；
12. 2B2A/2B2B/2C 转换核心已完成，不得重复模板、修订归链或另建转换器；累计除数
   仍不得脱离官方事件和登记日 RAW 单独使用；
13. TD-075 已关闭且 KR-2 已通过；不得重复 SSE 重复表、修订版、空白标题归链或
   差异化扣减回购股本规则；
14. KR-3A、KR-3B-1、KR-3B-2 已完成，不得另建四层模型、另写晋升状态机或绕开
   现有结果组装器；当前等待用户确认继续 KR-4～6 还是先做最小效果验证；
15. 每个 KR 独立完成五同步和强制闸门，K 线全链路完成后再迁移行业证据。

## 前端总清单分工（FW）

> 总状态见[前端总工作清单](../../03-modules/10-frontend/WORKLIST.md)。数据部只提供可验证事实，不定义界面文案。

| 协调项 | 本部门细分责任 | 验收证据 |
|:-------|:---------------|:---------|
| FW-020 | 为四层证据 API 提供唯一成功/失败事实、RAW/复权口径、`as_of`、采集时间、来源和冲突事实 | API 输入可追溯到冻结快照和逐源诊断；未知异常不伪装成功 |
| FW-022 | 提供 FINAL/PROVISIONAL 分离和收盘多源确认后的幂等晋升事实 | 同输入同 promotion ID；失败或冲突不晋升 |
| FW-040 | 提供真实行业、产业链位置、指标说明和比较数据 | 无前端硬编码排名、分位或产业链关系 |
| FW-050/060 | 为用户反馈与效果看板保留不可变行情、结果标签、失败分母和样本时间窗 | 点时数据无未来信息；缺失样本明确计入失败/拒答 |

## 2026-09-04 首页健康恢复交付

TD-082 后端已完成批次健康恢复和首页有效单源展示；来源验证在旁注，正式决策门禁不变。
TD-081 上游仍失败，独立端口板块 14.58s/503；指数三项新浪单源 200。
前端消费、SHA 集成路径、上游限制见[集成说明](../08-backend-api/HEALTH-RECOVERY-INTEGRATION.md)。
待前端联合验收后关闭债务，未修改现有预览。

### 板块快照候选与分类核验

同源快照适配器已于2026-09-05接入首页列表路由。496行业=31一级+128二级+337三级，概念504。
2026-09-06 同一适配器扩展至详情成分股：按板块BK代码完整分页，固定价格、涨跌幅、
资金流和as_of；BK1629/BK0475实测282/42条。未知数值保留null，不在数据层补0。
官方目录三级缺报价BK1362不能补0，不能把全部条目视为平行行业。
完整参数、分页哈希和目录核验见[第二轮证据](../08-backend-api/HEALTH-RECOVERY-INTEGRATION.md)。
用户已确认继续；HTTP已冻结category/as_of/source/delay字段与三类限制，待前端联合验收。

## 2026-09-07 FD-003 / FW-040 开发进展

2026-09-08：来源已获用户批准，Pydantic、HTTP和前端证据展开已接入。BK1629 AI四层、BK1650历史光通信子链正式目录可用。企业供货关系与其他板块覆盖仍待证据；详见docs/03-modules/10-frontend/chain-evidence/README.md。


## FW-041 用户下发：产业投资研究全景重构（2026-09-08）

总状态及完整需求见[FW-041唯一总表](../../03-modules/10-frontend/WORKLIST.md#fw-041-产业投资研究全景重构2026-09-08-用户下发)。本部门任务已登记，未启动实现。

- 本部门责任：当前行业事实、细分节点、公司实际业务映射与来源更新机制。
- 交付与验收：观察/披露时间分离；需求/订单/产能/价格/毛利证据及缺口；历史结构不能冒充当前瓶颈。
- 上游依赖：已批准公开资料范围。
- 交接纪律：研究方案先于接口，后端契约冻结提交先于前端；不得将历史行业分类图标为当前瓶颈研究完成。既有来源授权沿用，新增资金默认值/超范围来源另行审定。

FW-041补充：多维个股研究应分别覆盖盈利质量、估值、成长、财务风险、产业位置与行情，说明指标标准、时间和缺项；不得按涨幅冒充AI评级。当前前端仅先取消旧字母并添加行情分类分页。详见FW-041总表的多维个股研究补充。

FW-041入口细化：用户明确多维研究需前置到板块选股区，不能只放个股详情。本部门任务：提供板块范围公司多维指标与可比较口径、观察/披露时间和业务节点映射；数据缺项明确标注。 具体验收与唯一状态见前端WORKLIST中的“FW-041 板块页多维选股区”。已登记，尚未实现。

## FW-070 导航整合任务（2026-09-09）

用户批准六主入口和底部数据状态/设置，已登记待办，尚未实现。本部门责任：梳理市场/行业/选股/持仓所需数据覆盖与统一口径，复用FW-041多维指标，列出缺口。 上游依赖、完整范围及验收以[FW-070总表](../../03-modules/10-frontend/WORKLIST.md#fw-070-导航与投资工作流程整合2026-09-09-已批准)为准。先盘点能力，再按契约和页面就绪程度分阶段交付。
