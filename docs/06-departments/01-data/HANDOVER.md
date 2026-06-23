---
department: 数据管道部
codebase: src/data/
last_updated: 2026-06-21
---

# 🗄️ 数据管道部工作交接

## 当前状态

### 模块完成度

| 子系统 | 状态 | 说明 |
|:-------|:----:|:------|
| Provider 抽象层（4 文件） | ✅ | AKShareSource / AData / ZzShareSource / FallbackSource |
| DataCollector 封装 | ✅ | 6 类数据，API 向后兼容 |
| 数据缓存（DataCache） | ✅ | 内存 TTL，各类型独立过期时间 |
| 数据模型（7 个 Pydantic） | ✅ | StockQuote / KLine / NewsItem / Sector 等 |
| HealthStats 健康监控 | ✅ | 成功率/延迟/错误统计，/api/health 暴露 |
| 数据源审计 | ✅ | DATA_SOURCE_AUDIT.md 覆盖 10+ 平台 |

### 测试

| 测试集 | 测试数 | 覆盖率 |
|:-------|:------:|:------:|
| Provider 层单元测试 | 84 | 平均 83%（adata→83%, akshare→90%, fallback→100%） |
| 数据模型测试 | 22 | 100% |
| 契约测试 data→debate | 4 | JSON roundtrip + format_market_brief |

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

### 基本面深度（FD 系列，2026-06-23 新增）

> 完整背景见 [FUNDAMENTAL_RESEARCH.md](../../02-requirements/FUNDAMENTAL_RESEARCH.md)。

| FD | 事项 | 依赖 | 预估 |
|:--:|:-----|:----|:----:|
| **FD-001a** 🥇 | **数据模型扩展** — 新增 `FinancialMetric` / `IndustryPosition` / `SupplyChainNode` Pydantic 模型 | 无 | ~1h |
| **FD-001b** 🥇 | **Provider 协议扩展** — DataSource Protocol 新增 `get_financial_metrics()` + `get_industry_position()` | FD-001a | ~1h |
| **FD-001c** 🥇 | **AKShare 实现** — 用 `stock_financial_analysis_indicator` 实现财务指标 + 行业分类实现产业链定位 | FD-001b | ~2h |
| **FD-001d** 🥇 | **Collector 方法** — 新增 `get_financial_metrics()` + `get_industry_position()`，TTL=24h | FD-001b | ~1h |
| **FD-001e** 🥇 | **填充基本面占位符** — `format_market_brief()` 替换"暂无基本面数据"为真实数据 | FD-001c | ~1h |
| **FD-003** 🥈 | **供应链数据调研** — 评估年报 PDF 解析前5大客户/供应商的可行性 | 无 | ~2h |

### 数据流变更

```
新增数据流：
akshare.stock_financial_analysis_indicator(code)
     ↓
AKShareSource.get_financial_metrics(code)          ← Provider 协议
     ↓
DataCollector.get_financial_metrics(code)            ← 缓存 TTL=24h
     ↓
format_market_brief() → brief.sections["fundamentals"]  ← 填充占位符
     ↓
DebateState.market_data["financials"]               ← 辩论引擎消费

akshare 行业分类 + 主营业务构成
     ↓
AKShareSource.get_industry_position(code)           ← Provider 协议
     ↓
DataCollector.get_industry_position(code)
     ↓
后端 API / 辩论引擎                                 ← 下游消费
```

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
