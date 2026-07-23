---
department: 数据管道部
codebase: src/data/
last_updated: 2026-07-23 (FD-002)
---

# 🗄️ 数据管道部工作交接

## 当前状态

### 模块完成度

| 子系统 | 状态 | 说明 |
|:-------|:----:|:------|
| Provider 抽象层（4 文件） | ✅ | AKShareSource / AData / ZzShareSource / FallbackSource |
| DataCollector 封装 | ✅ | 6 类数据，API 向后兼容 |
| 数据缓存（DataCache） | ✅ | 内存 TTL，各类型独立过期时间 |
| 数据模型（10 个 Pydantic） | ✅ | StockQuote / KLine / NewsItem / BoardInfo / CapitalFlowItem / FinancialMetrics / MarketBrief / BriefSection / ValuationMetrics |
| HealthStats 健康监控 | ✅ | 成功率/延迟/错误统计，/api/health 暴露 |
| 数据源审计 | ✅ | DATA_SOURCE_AUDIT.md 覆盖 10+ 平台 |

### 测试

| 测试集 | 测试数 | 覆盖率 |
|:-------|:------:|:------:|
| Provider 层单元测试 | 84 | 平均 83%（adata→83%, akshare→90%, fallback→100%） |
| 数据模型测试 | 31 | 100%（含 ValuationMetrics 9 测试） |
| 契约测试 data→debate | 4 | JSON roundtrip + format_market_brief |
| DataCollector 测试 | 81 | 含 get_valuation 8 测试 |

### 关键架构决策

- **四源架构**：akshare（主）→ adata（免费备）→ zzshare（兼容备）→ Fallback（自动切换）
- **零成本优先**：所有数据源免费，无 Tushare Pro 付费依赖
- **零造假数据**：全链路真实数据，无硬编码 mock

---

## 开放债务

| ID | 描述 | 优先级 | 预估 |
|:---|:-----|:------:|:----:|
| TD-034 | zzshare.py 死条件逻辑（两边值一样） | 🟢 | 5min |
| TD-041 | 数据新鲜度标注 — KLine/Quote 采集时间戳 + 前端展示 | 🟡 | 2h |
| TD-057 | Provider 层测试（zzshare 46% 待补） | 🟡 | 30min |
| TD-047 | collector health_stats 异常文本（已修复 ✅） | — | — |
| TD-032 | FallbackSource 恢复主源（已修复 ✅） | — | — |

---

## 下一步优先级

### 现有债务

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 🟡 | TD-041 数据新鲜度标注 — 给 KLine/Quote 加 `fetched_at` | 无 |
| 2 🟢 | TD-034 修 zzshare 死条件 | 无 |
| 3 🟢 | TD-057 补 zzshare 测试到 ≥80% | 无 |

### 基本面深度 — 下放任务（⬜ 待办）

> 数据层 FD-001a~e 全部完成 ✅，辩论注入 FD-001f/g（辩论引擎部）也已完成。
> 以下为数据管道部剩余的 FD 待办，按优先级排列：

| 优先级 | 事项 | 预估 | 说明 |
|:------:|:-----|:----:|:------|
| 🥇 P0 | **FD-001h 多源财务数据** — ADataSource + ZzshareSource 实现 `get_financials()` | ~1h | 当前返回 `[]`，需各源实现 |
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
| **FD-001h** 🥇 | **多源财务数据** — ADataSource + ZzshareSource 实现 `get_financials()`（当前返回 `[]`） | ⬜ **待办** | FD-001c | ~1h |
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

待扩展：
ADataSource.get_financials() / ZzshareSource.get_financials()  ← ⬜ FD-001h（数据部）
ValuationMetrics (PE/PB/PS)  ← DataCollector.get_valuation()  ✅ FD-002（数据部 · 纯计算）

---

## 关键文件索引

| 文件 | 说明 |
|:-----|:------|
| `src/data/collector.py` | 统一数据采集入口（469 行） |
| `src/data/models.py` | 7 个 Pydantic 数据契约（140 行） |
| `src/data/cache.py` | 内存 TTL 缓存 |
| `src/data/providers/base.py` | DataSourceProtocol 抽象基类 |
| `src/data/providers/akshare.py` | AKShare 主数据源 |
| `src/data/providers/adata_source.py` | AData 免费数据源 |
| `src/data/providers/zzshare.py` | ZzShare 兼容数据源 |
| `src/data/providers/fallback.py` | 故障自动切换（已修复自动恢复） |
| `docs/06-departments/01-data/ROLE.md` | 👤 数据管道部角色定义 |
| `docs/06-departments/01-data/STANDARDS.md` | 📐 数据管道部技术规范 |
