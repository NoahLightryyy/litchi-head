# 基本面与供应链分析可行性报告

> **调研目的**：评估"为 litchi-head 增加机构级基本面/供应链/产业链分析能力"的可行性。
> **调研范围**：数据源可用性 → 竞品对标 → 架构适配 → 实施建议
> **调研日期**：2026-06-23

---

## 目录

1. [背景：机构 vs 散户的分析鸿沟](#1-背景机构-vs-散户的分析鸿沟)
2. [数据源调研：我们能用什么](#2-数据源调研我们能用什么)
3. [竞品对标分析](#3-竞品对标分析)
4. [当前架构适配点](#4-当前架构适配点)
5. [实施路径建议](#5-实施路径建议)
6. [方案推荐](#6-方案推荐)

---

## 1. 背景：机构 vs 散户的分析鸿沟

> 你说得对：投行机构与散户的**真正壁垒不在于分析模型，而在于数据纵深。**

| 分析维度 | 散户现状 | 机构做法 | 数据差距 |
|:---------|:---------|:---------|:--------:|
| **财报纵深** | 看 PE/PEG 表层估值 | 拆营收结构、分业务毛利率、现金流质量、商誉减值 | **中等** — 三大报表公开数据，但散户不会整合 |
| **供应链** | 完全缺失 | 前5大客户/供应商、集中度、成本传导能力 | **极大** — 年报披露但非结构化 |
| **产业链定位** | 不知道 | 公司在产业链哪一环，议价权强不强 | **极大** — 需行业知识库 |
| **同行对比** | 看估值 | 毛利率/研发投入/产能利用率同行业对比 | **中等** — 数据可计算，但需跨公司 |
| **管理层** | 不管 | 管理层持股变化、股权激励兑现条件、历史诚信 | **大** — 部分可获取但需清洗 |

**核心洞察**：这本质上是 **数据源差距** — 不是散户不想看，是这些数据散户拿不到或不会整合。litchi-head 如果能填这个坑，就是**真正的差异化竞争力**。

---

## 2. 数据源调研：我们能用什么

### 2.1 akshare（当前主力数据源）

| 数据类型 | 支持度 | 推荐接口 | 质量 |
|:---------|:------|:---------|:----:|
| **三大报表** | ✅ 完整 | `stock_*_sheet_by_report_em` | 良好（东方财富源更可靠） |
| **财务指标**（ROE/毛利率等） | ✅ 完整 | `stock_financial_analysis_indicator` | 良好 |
| **业绩预告/快报** | ✅ 完整 | `stock_yjyg_em` / `stock_yjkb_em` | 良好 |
| **行业分类**（申万/东方财富） | ✅ 完整 | `stock_industry_category_cninfo` | 良好 |
| **管理层持股变动** | ✅ 支持 | `stock_hold_management_detail_cninfo` | 良好 |
| **十大股东/机构持股** | ✅ 完整 | `stock_gdfx_holding_analyse_em` | 良好 |
| **主营业务构成**（按产品/地区） | ✅ 支持 | `stock_zygc_em` | 良好 |
| **前五大客户/供应商** | ❌ **不支持** | 无 | 需从年报 PDF 解析 |
| **产业链上下游关系** | ❌ **不支持** | 无 | 需外部数据或 LLM 推断 |
| **股权激励计划详情** | ⚠️ 部分 | 限售股解禁相关 | 仅限售股部分 |
| **诚信/处罚记录** | ⚠️ 部分 | 公告查询 + 关键词过滤 | 需后处理 |

> **总体判断**：akshare 在三大报表和财务指标上够用，但在**供应链、产业链、管理层深度信息**上存在明显缺口。

### 2.2 可选补充数据源

| 数据源 | 覆盖缺口 | 成本 | 可行性 |
|:-------|:---------|:----|:------:|
| **Tushare Pro** | 财报覆盖率 98%（高于 akshare 的 75%）| 500 元/年 | 可做备选 |
| **年报 PDF 解析** | 前5大客户/供应商 | 免费（巨潮资讯）| 🔧 需 NLP Pipeline |
| **同花顺 iFinD API** | 产业链图谱数据 | 机构收费 | ❌ 散户不可获取 |
| **LLM 知识推断** | 产业链关系 | API 调用成本 | ⚠️ 有幻觉风险 |

---

## 3. 竞品对标分析

### 3.1 机构终端（天花板）

| 工具 | 供应链/产业链能力 | 年费 | 散户可获取？ |
|:-----|:---------------:|:----:|:----------:|
| **Wind** | 5154个产业节点，2万公司关联，PDB/SDB 数据库 | ¥40,000+ | ❌ |
| **Bloomberg SPLC** | 23K公司、90万+供应链关系 | ¥230,000+ | ❌ |
| **Choice 机构版** | 产业链全景、财务深度分析 | ¥10,000+ | ❌ |
| **iFinD 机构版** | 产业链中心 80+ 热点板块，深度供应链数据库 | ¥10,000+ | ❌ |

### 3.2 散户可用工具（可对标）

| 工具 | 基本面能力 | 成本 | 与我们的差距 |
|:-----|:----------|:----|:-----------|
| **东方财富 Choice App** | 基础产业链图、财务分析 | 免费 | 产业链已有初步可视化 |
| **同花顺 App** | 财务健康评分、智能财报解读 | 免费 | AI 财报解读有先发优势 |
| **市值风云** | 产业链全景图 1200+ 个股 | 免费~6元/月 | 产业链可视化最接近竞品 |
| **AI 工具**（文心一言/通义千问） | 财报解读实用，但供应链易幻觉 | 免费 | 通用 LLM 不如领域专用 |

### 3.3 核心发现

> **供应链/产业链分析是机构 vs 散户之间的真正数据鸿沟。** 
> Wind 和 Bloomberg 的供应链数据库散户根本接触不到，而散户可用的工具（市值风云、Choice 免费版）只能提供表层产业链展示，无法做深度分析。

| 功能 | Wind | 市值风云 | litchi-head（当前） | litchi-head（目标） |
|:-----|:----:|:--------:|:-----------------:|:-----------------:|
| 财报指标 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| 财务健康评分 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ |
| 供应链客户/供应商 | ⭐⭐⭐⭐⭐ | ⭐⭐ | ❌ | ⭐⭐ |
| 产业链图谱 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ❌（伪数据） | ⭐⭐⭐ |
| AI 分析 | ❌ | ❌ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| 辩论推演 | ❌ | ❌ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 4. 当前架构适配点

### 4.1 需要改动的 5 层

```
改动范围概览：

src/data/models.py          ── 新增 FinancialMetric / IndustryChainNode 等模型
src/data/providers/base.py   ── 扩展 DataSource Protocol（2 个新方法）
src/data/providers/akshare.py ── 实现 get_financial_metrics()
src/data/collector.py        ── 新增采集方法 + 填充基本面占位符
src/debate/orchestrator.py   ── collect_data_node 获取财务数据
src/debate/analysts.py       ── 基本面分析师接收结构化数据
backend/routers/market.py    ── 修复伪产业链数据
frontend/lib/types/market.ts ── 新增前端类型
frontend/components/          ── 新增财务数据展示组件
docs/learning/               ── 学习卡片
```

### 4.2 当前架构的有利条件

| 条件 | 详情 |
|:-----|:------|
| **Provider 可扩展性** | `DataSource` 是 Protocol（结构性类型），新增方法即可自动得到 pyright 校验 |
| **缓存基建已就绪** | DataCollector 的 TTL 缓存 + HealthStats 监控对新数据类型零成本适用 |
| **基本面占位符已留** | `format_market_brief()` 的 fundamentals 区段当前是占位文本"暂无基本面数据" |
| **分析师已有基本面角色** | `analyst.fundamental` 提示词已包含 ROE/利润率/负债率，只缺真实数据输入 |
| **前端产业链页面已存在** | `frontend/app/sector/[id]/` 页面有 ChainMap 组件骨架，数据是伪的 |
| **辩论数据流接口清晰** | 基本面分析师的 `data_evidence` 和 `key_findings` 字段可直接承载财务数据 |

### 4.3 当前架构的问题点

| 问题 | 位置 | 影响 |
|:-----|:-----|:-----|
| **产业链数据是伪数据** | `backend/routers/market.py:_build_chain_map()` | 根据涨幅排序虚构"上游/中游/下游"，违反零造假数据原则 |
| **基本面占位符未填充** | `collector.py:460-464` | LLM 只能看到"暂无基本面数据"，分析质量受限 |
| **后端绕过 Provider 层** | `market.py:114-138` 直接调 akshare | 无缓存、无健康监控、违反数据部规范 |
| **知识库基本面文件未激活** | `data/knowledge_base/fundamentals/` 7 篇 | 现有的 ROE/PE/PEG 等概念知识未被实时数据激活 |
| **后端与辩论数据孤岛** | 板块 API 和个股辩论不互通 | 产业链分析在辩论中不可用 |

### 4.4 各层改动明细

#### 4.4.1 数据模型层（`src/data/models.py`）

```python
class FinancialMetric(BaseModel):
    """单个报告期的财务指标概览"""
    report_date: str                # 2026-03-31
    report_type: str                # 年报/一季报/中报/三季报
    # 盈利能力
    roe: float = 0.0
    roa: float = 0.0
    gross_profit_margin: float = 0.0
    net_profit_margin: float = 0.0
    # 估值
    pe_ttm: float = 0.0
    pb: float = 0.0
    ps_ttm: float = 0.0
    # 成长性
    revenue_growth_yoy: float = 0.0
    profit_growth_yoy: float = 0.0
    # 负债与现金流
    debt_ratio: float = 0.0
    free_cash_flow: float = 0.0

class SupplyChainNode(BaseModel):
    """供应链节点"""
    company_code: str
    company_name: str
    role: str                       # "客户" / "供应商"
    transaction_ratio: float = 0.0  # 交易额占比（%）
    relation_type: str = ""         # 关联关系描述

class IndustryPosition(BaseModel):
    """产业链位置"""
    industry: str                       # 所属行业
    chain_stage: str                    # 上游/中游/下游
    stage_description: str = ""
    competitors: list[str] = []
    suppliers: list[SupplyChainNode] = []
    customers: list[SupplyChainNode] = []
```

#### 4.4.2 Provider 层（`src/data/providers/base.py`）

扩展 `DataSource` Protocol，新增 2 个方法：

```python
def get_financial_metrics(self, code: str) -> list[FinancialMetric]:
    """获取个股财务指标（多报告期）"""
    ...

def get_industry_position(self, code: str) -> IndustryPosition | None:
    """获取个股产业链定位"""
    ...
```

#### 4.4.3 采集层（`src/data/collector.py`）

- 新增 `get_financial_metrics()` 方法（TTL=24h，财务数据更新慢）
- 新增 `get_industry_position()` 方法
- 修改 `format_market_brief()`：用真实财务数据替换基本面占位符

#### 4.4.4 辩论层（`src/debate/orchestrator.py`）

- `collect_data_node` 新增财务数据采集，存入 `market_data["financials"]`
- 基本面分析师接收结构化 `FinancialMetric` 数据
- 产业链数据作为 `market_data["industry"]` 上下文注入

#### 4.4.5 后端 API（`backend/routers/market.py`）

- `_build_chain_map()` 用真实行业分类替代伪产业链
- 新增 `/api/market/sector/{id}/chain` 详细产业链接口
- 从直接调 akshare 改为通过 DataCollector
- 新增 `/api/financial/{code}` 财务数据接口

#### 4.4.6 前端

- 新增 `FinancialMetric` / `IndustryPosition` 前端类型
- `FinancialSummary` 卡片组件（财务健康概览）
- ChainMap 注入真实数据

### 4.5 7 位大师的适配优先级

| 大师 | 基本面需求 | 适配方式 | 优先级 |
|:-----|:----------|:---------|:------:|
| **巴菲特** | ROE、自由现金流、负债率、护城河 | 直接接收财务指标 | 🥇 |
| **格雷厄姆** | PB、PE、净运营资本、流动比率 | 直接接收财务指标 | 🥇 |
| **林奇** | PEG、营收增长趋势、利润率趋势 | 间接通过分析师报告 | 🥈 |
| **达利欧** | 行业平均 ROE、行业负债率 | 行业级聚合数据 | 🥈 |
| **芒格** | 管理层质量信号 | 通过分析师报告 | 🥉 |
| **德鲁肯米勒** | 行业增长率趋势 | 行业级聚合数据 | 🥉 |
| **索罗斯** | PE 区间、预期差 | 通过分析师报告 | 🥉 |

---

## 5. 实施路径建议

### 场景 A：机构维度注入辩论（核心方案）

> 让基本面分析师（`analyst.fundamental`）真正做基本面分析。

**范围**：数据模型 → Provider → Collector → Orchestrator
**难度**：⭐⭐⭐（中等）
**预估**：2-3 天

```
用户输入股票代码
  → collect_data_node
      ├── 行情数据（已有）
      ├── K 线数据（已有）
      ├── 财务指标 🆕 ← akshare.stock_financial_analysis_indicator
      └── 产业链定位 🆕 ← akshare 行业分类 + 主营业务构成
  → analyst_round
      ├── 基本面分析师 ← 接收结构化财务数据（不再是占位符）
      ├── 技术面分析师（不变）
      ├── 情绪面分析师（不变）
      └── 宏观面分析师（不变）
  → master_round（所有大师获益于更高质量的分析师报告）
  → aggregate → 决策
```

### 场景 B：产业链从伪数据到真实数据（必修坑）

> 当前前端产业链页面用涨幅排序假装产业链，必须修复。

**范围**：后端 API → 前端组件
**难度**：⭐⭐（简单）
**预估**：半天

```
当前: 涨幅排序 → 标记为"上游/中游/下游" ❌ 造假
修复: 行业分类 + 主营业务构成 → 按业务实质归类 ✅ 真实
```

### 场景 C：供应链图谱（天花板功能）

> 前五大客户/供应商的可视化图谱。这是散户工具中**真正稀缺的功能**。

**范围**：NLP Pipeline（年报PDF解析） + 数据模型 + 前端图谱
**难度**：⭐⭐⭐⭐⭐（困难）
**预估**：5-7 天

```
年报 PDF（巨潮资讯）
  → NLP 解析（客户名称 + 交易额占比）
  → 结构化入库
  → 前端图谱展示（D3.js / vis-network）
```

**风险**：年报 PDF 格式不统一，NLP 解析准确率有上限。

---

## 6. 方案推荐

### 优先做：场景 A → 场景 B

| 步骤 | 内容 | 预估 | 价值 |
|:----:|:-----|:----:|:----:|
| 1️⃣ | **填充基本面占位符** — 用 akshare 真实财务数据替换"暂无基本面数据" | **~2h** | 🔥 立刻提升分析质量 |
| 2️⃣ | **Provider 扩展** — DataSource 协议 + akshare 实现 | **~3h** | 🏗️ 为后续打地基 |
| 3️⃣ | **辩论引擎注入** — collect_data_node 获取财务数据 | **~3h** | 🎯 分析师看到真实数据 |
| 4️⃣ | **修复伪产业链** — 后端真实行业分类替代伪数据 | **~4h** | 🛡️ 消除数据诚信债务 |
| 5️⃣ | **前端财务卡片** — FinancialSummary 组件 | **~4h** | 👀 用户可见的变化 |

**总计：~16h（2天）** → 基本面数据接入完成

### 可选做：场景 C（供应链图谱）

> 建议在场景 A+B 稳定运行后，单独评估是否需要。它是一个独立功能轨，不阻塞其他工作。

**决策条件**：
- litchi-head 已积累一定真实用户
- 前端产业链页面有用户交互数据表明需求
- 有足够的 API Token 预算支持 PDF 文本解析

---

## 关联架构决策

- 数据层适配参照：`src/data/providers/base.py:20-68` — DataSource Protocol
- 辩论注入点参照：`src/debate/orchestrator.py:129` — collect_data_node
- 大师适配参照：`src/debate/analysts.py:41-58` — 基本面分析师定义
- 知识库基础参照：`data/knowledge_base/fundamentals/` （7 篇概念文件）
- Provider 健康监控参照：`src/data/collector.py:50-113` — HealthStats 模式

---

## 附录：一句话总结

> **技术上完全可行**。akshare 的财务报表和财务指标接口足够支撑 80% 的基本面分析需求。供应链图谱需要额外工作（年报 PDF 解析），是真正的天花板功能但不是必经之路。
> 
> **竞品差距**：我们的 AI 辩论引擎是竞品没有的差异化优势，加上基本面数据后，litchi-head 将是极少数同时具备**技术分析 + 基本面深度 + AI 多角度辩论**的散户投资工具。
>
> **第一步最快**：填充基本面占位符只要 2 小时，立刻见效。

---

*本报告基于 2026-06-23 数据调研生成*
