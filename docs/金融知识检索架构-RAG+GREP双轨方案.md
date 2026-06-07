# 📚 金融知识检索架构：RAG + GREP 双轨方案

> 设计方案 · 2026-06-07
> 关联：ADR-006（三层记忆）| ADR-009（MCP 工具扩展）| `src/memory/` | `src/data/`

---

## 目录

- [1. 问题定义](#1-问题定义)
- [2. 双轨方案总览](#2-双轨方案总览)
- [3. Track A：RAG 语义检索（金融文本类）](#3-track-arag-语义检索金融文本类)
- [4. Track B：GREP 精确检索（公式/代码类）](#4-track-bgrep-精确检索公式代码类)
- [5. 架构总图](#5-架构总图)
- [6. 与现有模块的关系](#6-与现有模块的关系)
- [7. 数据目录结构](#7-数据目录结构)
- [8. 阶段实施计划](#8-阶段实施计划)
- [9. 技术选型依据](#9-技术选型依据)

---

## 1. 问题定义

### 1.1 两类金融知识

金融投资领域的知识天然划分为两种类型，**单一方案无法同时解决**：

| 维度 | 金融文本类（Track A） | 公式/代码类（Track B） |
|------|---------------------|----------------------|
| **本质** | 语义理解问题 | 精确匹配问题 |
| **例子** | "市场情绪转向谨慎"、"巴菲特谈护城河" | `PE = Price / EPS`、`MACD(12,26,9)` |
| **搜索方式** | 语义相似度（embedding） | 精确/正则匹配 |
| **查询特点** | "当前市场氛围怎么样？" → 语义相近的多种表达 | "MACD 计算公式是什么？" → 唯一正确答案 |
| **误报代价** | 低（相关即可） | 高（公式错了=交易错了） |
| **知识变化** | 持续更新（新闻、研报、市场观点） | 相对稳定（公式就是公式） |

### 1.2 现状

- `src/memory/` — 空模块（ADR-006 已规划三层记忆，但未落地）
- `src/data/` — 空模块（仅计划目录结构，无代码）
- 文档中已有 RAG 需求：教育小智 Agent + 大师 Agent 都需要语料检索
- 技术栈已有 FAISS + BGE-small-zh 的早期技术选型
- ADR-009 的 `get_tools()` 即将落地，是工具箱的自然挂载点

---

## 2. 双轨方案总览

```
┌─────────────────────────────────────────────────────────┐
│                    Agent 工具箱                          │
│  (通过 ADR-009 get_tools() 注入)                        │
│                                                         │
│   ┌──────────────────┐   ┌──────────────────┐           │
│   │  RAG Search Tool  │   │  GREP Code Tool  │           │
│   │  (语义检索)       │   │  (精确检索)      │           │
│   └──────┬───────────┘   └──────┬───────────┘           │
│          │                      │                       │
└──────────┼──────────────────────┼───────────────────────┘
           │                      │
           ▼                      ▼
┌──────────────────┐   ┌──────────────────┐
│  向量库 (FAISS)   │   │  代码索引         │
│  文本 → embedding │   │  公式/代码 → GREP │
│  语义搜索 top-k   │   │  正则/关键词匹配  │
└──────────────────┘   └──────────────────┘
```

### 2.1 核心原则

1. **按知识类型选轨道** — 文本走 RAG，公式/代码走 GREP，不混用
2. **工具化输出** — 两个轨道都封装为 ADR-009 的 Tool，Agent 通过 `get_tools()` 按需获取
3. **渐进增强** — Phase 0 纯文件 + Phase 1 向量库 + Phase 2 运维化
4. **零外部服务依赖** — FAISS（本地文件索引）+ GREP（纯字符串操作），MVP 阶段不部署向量数据库服务

---

## 3. Track A：RAG 语义检索（金融文本类）

### 3.1 适用场景

| Agent | 检索内容 | 典型查询 |
|-------|---------|---------|
| 🎓 教育小智 | 金融概念、指标解释、行业知识 | "什么是安全边际？"、"PE 和 PB 的区别" |
| 🧙 大师 Agent | 大师语录、投资原则、方法论 | "巴菲特对科技股怎么看？" |
| 🗞️ 新闻分析 | 历史类似事件、市场情绪参考 | "类似宏观环境下市场怎么走的？" |
| 📈 行情分析 | 技术形态识别参考 | "头肩顶形态的历史案例" |

### 3.2 数据流程

```
┌──────────┐    ┌───────────┐    ┌──────────┐    ┌───────────┐
│ 原始语料   │───▶ Chunk 切分 │───▶ Embedding │───▶ FAISS 索引  │
│ .md / .txt │    │ 512 tokens │    │ BGE-small │    │ .faiss文件  │
└──────────┘    └───────────┘    └──────────┘    └──────────┘
                                                       │
                               Agent 查询 ──────────────┤
                                                       ▼
                                               ┌──────────┐
                                               │ top-k 结果 │──▶ LLM 上下文注入
                                               └──────────┘
```

### 3.3 技术选型

| 组件 | 方案 | 理由 |
|------|------|------|
| **向量库** | **FAISS**（`faiss-cpu`） | 轻量、零部署、文件级存储、MVP 够用 |
| **嵌入模型** | **BGE-small-zh** | 中文效果好、模型小（~30MB）、`sentence-transformers` 一行加载 |
| **Chunk 策略** | 按 Markdown 标题分块 + 512 token 窗口重叠 10% | 金融文档结构清晰，标题天然分割点 |
| **检索策略** | 向量相似度 top-5 + 按时间衰减加权 | 近期知识权重更高（与 ADR-006 对齐） |
| **存储格式** | `.faiss`（向量索引）+ `metadata.json`（原文映射） | 可版本控制、可复制、零运维 |

### 3.4 核心接口设计

```python
# src/memory/knowledge_base.py — RAG 知识库（Phase 1 实现）

class KnowledgeBase:
    """金融文本知识库 —— 基于 FAISS 的语义检索"""

    def __init__(self, index_path: str = "data/knowledge_base"):
        self.index_path = Path(index_path)
        self.index: faiss.Index | None = None
        self.metadata: list[dict] = []   # chunk_id → {source, text, type, timestamp}
        self.embedder = self._init_embedder()

    def _init_embedder(self) -> SentenceTransformer:
        """加载 BGE-small-zh 嵌入模型"""
        ...

    def ingest(self, file_path: str, knowledge_type: str = "general"):
        """导入一个知识文件（.md / .txt）
        1. 读取文件
        2. 按 Markdown 标题分块
        3. 计算 embedding
        4. 追加到 FAISS 索引
        """
        ...

    def search(self, query: str, k: int = 5, knowledge_type: str | None = None) -> list[dict]:
        """语义检索 top-k 结果
        1. query → embedding
        2. FAISS 相似度搜索
        3. 按时间衰减加权重排序
        4. 返回 {text, source, score, timestamp}
        """
        ...

    def save(self):
        """持久化到磁盘"""
        ...

    def load(self):
        """从磁盘加载"""
        ...
```

---

## 4. Track B：GREP 精确检索（公式/代码类）

### 4.1 适用场景

| Agent | 检索内容 | 典型查询 |
|-------|---------|---------|
| 🎓 教育小智 | 指标公式、计算逻辑 | "MACD 的公式是什么？"、"KDJ 怎么算的？" |
| 📈 行情分析 | 技术指标实现、参数含义 | "布林带的中轨是哪条线？" |
| 🛠️ 开发者 | 已有代码片段、配置项 | "哪里定义了 PE 的计算？"、"回测的止损逻辑在哪？" |

### 4.2 为什么不用 RAG 做公式搜索

对比实验来说明：

```
查询: "PE = Price / Earnings"
  RAG（语义）: 返回 "市盈率是衡量公司估值的指标..."        ❌ 相关但不精确
  GREP（精确）: 返回 "PE = Price / EPS"                   ✅ 精确命中
```

公式和代码**定义了就是定义了**，不需要"相似"——你需要的是**精确的那个**。

### 4.3 技术方案

GREP + 结构化索引，两层加速：

```python
# src/data/formula_index.py — 公式/代码索引（Phase 1 实现）

class FormulaIndex:
    """公式与代码索引 —— 靠 GREP + 预计算索引，不需要向量"""

    def __init__(self, root_path: str = "data/knowledge_base/formulas"):
        self.root = Path(root_path)
        self.index: dict[str, list[tuple[str, int]]] = {}  # keyword → [(file, line)]

    def build_index(self):
        """扫描公式目录，预构建关键词倒排索引
        关键词提取规则：大写单词、数字+字母组合、运算符等
        例: "MACD(12, 26, 9)" → 索引词: ["MACD", "12", "26", "9"]
        """
        ...

    def search(self, query: str, exact: bool = True) -> list[dict]:
        """公式/代码精确搜索
        exact=True  : 精确匹配（用户明确知道要找什么）
        exact=False : 关键词组合搜索（索引加速的 GREP）
        返回 {file, line, content, formula_name}
        """
        ...

    def grep(self, pattern: str, path: str | None = None) -> list[dict]:
        """底层 GREP（暴露给高级用法）
        使用 re.search 进行正则匹配
        """
        ...
```

### 4.4 公式库内容示例

```
data/knowledge_base/formulas/
├── README.md                     # 索引说明
├── technical_indicators.md       # 技术指标公式
│   ├── MACD(12, 26, 9)
│   ├── KDJ(9, 3, 3)
│   ├── RSI(14)
│   ├── 布林带(20, 2)
│   └── ...
├── fundamental_ratios.md         # 基本面比率
│   ├── PE = Price / EPS
│   ├── PB = Price / Book Value
│   ├── ROE = Net Income / Equity
│   ├── ROA = Net Income / Assets
│   ├── D/E Ratio = Debt / Equity
│   └── ...
├── risk_metrics.md               # 风险指标
│   ├── VaR(95%, 1d)
│   ├── Sharpe Ratio
│   ├── Max Drawdown
│   └── Beta
└── strategy_formulas.md          # 策略相关公式
    ├── 网格交易间距
    ├── 金字塔加仓公式
    └── ...
```

公式库的每个条目格式：

```markdown
## MACD（指数平滑异同移动平均线）

**公式**：
```
EMA(12) = 前一日EMA(12) × 11/13 + 今日收盘价 × 2/13
EMA(26) = 前一日EMA(26) × 25/27 + 今日收盘价 × 2/27
DIF = EMA(12) - EMA(26)
DEA = 前一日DEA × 8/10 + 今日DIF × 2/10
MACD柱 = (DIF - DEA) × 2
```

**参数**：12日快线、26日慢线、9日信号线

**使用方式**：`talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)`

**解读**：
- DIF 上穿 DEA → 金叉（买入信号）
- DIF 下穿 DEA → 死叉（卖出信号）
- MACD柱由负转正 → 多头动能增强
```

这种格式特点是：
- **人类可读**：Markdown 直接展示
- **机器可检索**：GREP 可以搜 `MACD`、`EMA`、`12` 等关键词
- **嵌套在 RAG 知识库中**：同样可以被 RAG 索引到（双轨并行）

---

## 5. 架构总图

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Agent 层                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ 新闻分析  │  │ 行情分析  │  │ 教育小智  │  │ 大师Agent│  ...       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘             │
│       │             │             │             │                    │
└───────┼─────────────┼─────────────┼─────────────┼────────────────────┘
        │             │             │             │
        │        ┌────┴─────────────┴────┐        │
        │        │  ADR-009 get_tools()  │        │
        │        └────┬─────────────┬────┘        │
        │             │             │             │
        ▼             ▼             ▼             ▼
┌──────────────┐ ┌──────────────────────────────────────────┐
│  外部数据源   │ │          知识检索层                       │
│  · akshare   │ │                                          │
│  · 同花顺     │ │  ┌─────────────────┐  ┌───────────────┐  │
│  · 新闻API   │ │  │  RAG Semantic   │  │  GREP Exact   │  │
└──────────────┘ │  │  Search         │  │  Search       │  │
                 │  │                 │  │               │  │
                 │  │  FAISS + BGE    │  │  倒排索引      │  │
                 │  │  语义检索 top-k  │  │  正则/关键词   │  │
                 │  └────────┬────────┘  └───────┬───────┘  │
                 │           │                   │          │
                 └───────────┼───────────────────┼──────────┘
                             │                   │
                             ▼                   ▼
                 ┌──────────────────┐  ┌──────────────────┐
                 │  data/           │  │  data/           │
                 │  knowledge_base/  │  │  formulas/       │
                 │  · 金融概念.md    │  │  · indicators.md │
                 │  · 大师语录.md    │  │  · ratios.md     │
                 │  · 行业知识.md    │  │  · risk.md       │
                 │  · FAISS 索引     │  │  · strategies.md │
                 └──────────────────┘  └──────────────────┘
```

---

## 6. 与现有模块的关系

### 6.1 `src/memory/`（ADR-006 三层记忆）

| 记忆层 | 已有规划 | RAG/GREP 的关系 |
|--------|---------|----------------|
| **工作记忆** | Session 上下文 | 独立，无交集 |
| **情景记忆** | 历史交易记录 | 独立，无交集 |
| **反思机制** | LLM 驱动复盘 | 反思结果可写入 RAG 知识库作为"经验知识" |
| **新：知识库** | 未规划 | **RAG 知识库作为第四记忆类型**，与三层并列 |

```
三层记忆架构（原）      扩展后
┌─────────────┐        ┌─────────────┐
│  工作记忆    │        │  工作记忆    │
├─────────────┤        ├─────────────┤
│  情景记忆    │        │  情景记忆    │
├─────────────┤        ├─────────────┤
│  反思机制    │        │  反思机制    │
└─────────────┘        ├─────────────┤
                       │  知识库      │ ◀── RAG + GREP（本方案）
                       │  · 金融文本  │
                       │  · 公式代码  │
                       └─────────────┘
```

### 6.2 `src/data/`（数据文件）

现有的目录规划与本方案直接对齐：

```
data/
├── master_corpus/          # （已有规划）大师语料库 → RAG 索引
│   ├── buffett.md
│   ├── munger.md
│   └── graham.md
├── knowledge_base/         # （已有规划）教育知识库 → RAG 索引
│   ├── indicators.md       # 技术指标解释
│   ├── concepts.md         # 金融概念
│   └── industries.md       # 行业知识
├── formulas/               # （本方案新增）公式知识库 → GREP 索引
│   ├── technical_indicators.md
│   ├── fundamental_ratios.md
│   └── risk_metrics.md
└── vector_index/           # （本方案新增）FAISS 向量索引文件
    ├── knowledge.index     # FAISS 二进制索引
    └── metadata.json       # 元数据映射
```

### 6.3 `src/agents/base.py`（ADR-009 get_tools）

RAG 和 GREP 都封装为 Tool，通过 `get_tools()` 挂载：

```python
class EducationAgent(BaseAgent):
    """教育小智 Agent"""

    def get_tools(self) -> list[Any]:
        return [
            Tool(
                name="knowledge_rag_search",
                func=knowledge_base.search,
                description="语义搜索金融知识库（概念、指标、行业知识）",
            ),
            Tool(
                name="formula_grep_search",
                func=formula_index.search,
                description="精确搜索公式和代码（指标公式、计算逻辑）",
            ),
        ]
```

---

## 7. 数据目录结构

完整的数据目录设计：

```
data/knowledge_base/                            ← 知识库根目录
│
├── concepts/                                   ← 金融概念
│   ├── 安全边际.md
│   ├── 护城河.md
│   ├── 复利效应.md
│   └── 资产配置.md
│
├── indicators/                                 ← 技术指标解释（文本版）
│   ├── MACD.md
│   ├── KDJ.md
│   ├── RSI.md
│   ├── 布林带.md
│   └── 均线系统.md
│
├── fundamentals/                               ← 基本面概念
│   ├── PE.md
│   ├── PB.md
│   ├── ROE.md
│   └── DCF.md
│
├── master_corpus/                              ← 大师语料
│   ├── buffett/
│   │   ├── 致股东信-2023.md
│   │   └── 核心原则.md
│   ├── munger/
│   │   ├── 穷查理宝典摘要.md
│   │   └── 投资原则.md
│   └── ...
│
├── industries/                                 ← 行业知识
│   ├── 半导体产业链.md
│   ├── 新能源汽车.md
│   └── 医药生物.md
│
├── formulas/                                   ← 公式库（GREP 轨道）
│   ├── README.md                               ← 索引说明
│   ├── technical_indicators.md                 ← 技术指标公式
│   ├── fundamental_ratios.md                   ← 基本面比率
│   ├── risk_metrics.md                         ← 风险指标
│   └── strategy_formulas.md                    ← 策略公式
│
└── vector_index/                               ← 向量索引（自动生成）
    ├── knowledge.index                         ← FAISS 索引文件
    └── metadata.json                           ← chunk 原文映射
```

---

## 8. 阶段实施计划

### Phase 0：基建期（现在）— 本方案的设计阶段

| 事项 | 状态 |
|------|------|
| ✅ 本设计文档 | **已完成** |
| ⬜ `src/memory/knowledge_base.py` — 空接口文件 + docstring | 10min |
| ⬜ `src/data/formula_index.py` — 空接口文件 + docstring | 10min |
| ⬜ `data/knowledge_base/formulas/` — 初始化公式库（第一批 ~20 条） | 30min |

### Phase 1：MVP 期 — 实现 RAG + GREP 核心（进行中）

| 事项 | 预估工时 | 前置依赖 | 状态 |
|------|---------|---------|:----:|
| RAG：`KnowledgeBase` 核心类（ingest/search/save/load） | ∼2h | ADR-009 `get_tools()` 已落地 | ✅ 已完成 |
| 知识库初始化：首批 7 篇知识 Markdown | ∼30min | 无 | ✅ 已完成 |
| 教育小智 Agent：XiaoZhiAgent | ∼2h | KnowledgeBase + LLM | 🔧 进行中 |
| GREP：`FormulaIndex` 核心类（build_index/search/grep） | ∼1h | 同上 | ⬜ |
| 公式库：首批 20+ 公式 Markdown | ∼30min | 无 | ⬜ |
| FAISS 索引构建脚本 + CI 集成 | ∼30min | `KnowledgeBase` 完成 | ⬜ |
| ADR‑009 Tool 包装 + Agent 集成 | ∼30min | 两个核心类完成 | ⬜ |
| 测试：RAG 检索测试 + GREP 检索测试 | ∼1h | 核心类完成 | ✅ 15 tests 通过 |

### Phase 2：迭代期 — 扩展与运维

| 事项 | 说明 |
|------|------|
| 知识库增量更新 | `ingest()` 支持追加而非重建 |
| 多知识源自动导入 | akshare 新闻自动入知识库 |
| 反思结果入知识库 | ADR-006 反思机制产出自动写入 |
| 切换到 Milvus/pgvector | 当 FAISS 索引超过 10 万条时 |
| 知识库质量监控 | 检索命中率、用户反馈评分 |
| 知识库批量扩充 | 见 §10 知识库扩充策略 |

---

## 9. 技术选型依据

### 9.1 为什么 FAISS 而不是 Milvus

| 维度 | FAISS（选） | Milvus（弃） |
|------|------------|-------------|
| 部署 | 无，本地文件 | 需要 Docker 部署服务 |
| 运维 | 零 | 需要管理服务、备份、监控 |
| MVP 够用 | 10 万条以下查询 <10ms | 适合百万级以上 |
| 迁移成本 | 数据结构兼容，后期可迁移 | 一次锁定 |
| Windows 兼容 | `faiss-cpu` 可安装（见坑点） | Docker 依赖 |

FAISS 不是"最终方案"，而是"MVP 最轻方案"。等知识库超过 10 万条时迁移到 Milvus 或 pgvector，数据可以一键导出。

### 9.2 为什么 BGE-small-zh

| 模型 | 参数量 | 中文效果 | 速度 | 加载方式 |
|------|--------|---------|------|---------|
| **BGE-small-zh**（选） | ~30MB | 优秀 | 最快 | `sentence-transformers` |
| BGE-base-zh | ~100MB | 更好 | 中 | 同上 |
| text2vec-large-chinese | ~300MB | 最好 | 慢 | 同上 |
| OpenAI embedding | API 调用 | 好 | 网络延迟 | 有费用 |

BGE-small-zh 在 Phase 1 的性价比最高——千条级别知识库的准确率差异不到 2%，但速度差 5 倍。

### 9.3 为什么 GREP 不是"倒退"

```
query = "MACD(12, 26, 9) 公式"
  RAG: "MACD 是一种趋势跟踪指标..."        ✅ 相关但不精确
  grep -rn "MACD" formulas/               ✅ 精确命中定义

query = "VAR模型参数设置"
  RAG: "VaR 是 Value at Risk 的缩写..."   ✅ 概念解释
  grep -rn "VaR" formulas/                ✅ 精确公式

query = "怎么算 Sharpe Ratio"
  RAG: "夏普比率衡量风险调整后收益..."     ✅ 适合文本解释
  grep -rn "Sharpe" formulas/             ✅ 精确公式
```

双轨并行不是冗余——**同一个查询，RAG 给"解释"，GREP 给"公式"**，两者互补。Agent 可以同时调用两个工具，把结果合并给用户。

---

## 10. 知识库扩充策略

> 2026-06-07 新增 — 经项目审视，手写知识文件效率低且覆盖面有限，以下为推荐的批量扩充路径。

### 10.1 问题

首批知识文件（7 篇）为手写，仅覆盖核心概念（安全边际、复利、护城河）、
基础指标（MACD、RSI）和基本面（PE、ROE）。要靠手写填满涵盖
100+ 知识点的金融知识库是不现实的。

### 10.2 四层扩充方案

```
四层策略：AI 生成 → 公开数据集 → API 实时 → 社区贡献
           Phase 1         Phase 2      Phase 2+    持续
```

#### 🥇 第一层：LLM 批量生成（Phase 1，48h 内完成）

利用项目自身的 DeepSeek 能力，批量生成高质量知识点文档。

**流程**：
1. 定义扩展知识清单（约 50 个知识点）
2. 构造结构化 prompt，指定 markdown 格式模板
3. 批量调用 LLM 生成，每批 5-10 篇
4. 人工抽查 + KnowledgeBase 自检（搜索同主题看是否语义一致）

**覆盖范围（首批扩展 30 篇）**：
- 概念：护城河深度展开（5 种护城河各 1 篇）、经济周期、通货膨胀、滞胀
- 指标：KDJ、布林带、均线(MA)、OBV、DMI、WR
- 基本面：PB、DCF、PEG、股息率、自由现金流
- 大师：巴菲特六原则、芒格二十五误判、彼得·林奇选股
- 策略：价值投资、成长投资、指数定投、网格交易、股债平衡

#### 🥇 第二层：公开中文金融数据集（Phase 1）

| 数据集 | 来源 | 内容 | 用法 |
|--------|------|------|------|
| **FinEval** | HuggingFace | 金融知识选择题/问答 | QA pair → 转换为知识 chunks |
| **FinanceQA** | GitHub | 中文金融问答对 | 同义改写为知识文档 |
| **CCF-金融知识图谱** | 开放平台 | 实体-关系三元组 | 转换为概念解释文档 |
| **招股书/研报摘要** | 爬虫收集 | 行业分析 | 经 LLM 摘要后入库 |

**注意**：公开数据集的质量参差不齐，需要经过清洗和格式转换。
建议脚本化处理：`scripts/import_dataset.py`。

#### 🥈 第三层：akshare 实时数据知识化（Phase 2+）

`akshare` 已安装，可以利用其 API 获取实时金融信息补充知识库。

**可自动化采集**：
- 宏观指标：CPI、PPI、GDP、PMI（定期自动更新解释文档）
- 行业数据：申万行业分类、行业指数成分
- 公司信息：A 股公司简介（过滤后入库）

#### 🥉 第四层：社区贡献 + 用户反馈驱动（持续）

未来 Agent 对话中，如用户问了知识库未覆盖的问题：
1. LLM 现场搜索/生成答案
2. 触发`ingest()`自动入库
3. 人工审核后确认

形成 "问答 → 发现知识缺口 → 自动补充 → 人工确认" 的闭环。

### 10.3 分步执行计划

| 步骤 | 操作 | 产出 | 预估 |
|:----:|------|------|:----:|
| 1 | 定义 50 个知识点清单 | `docs/knowledge_inventory.md` | 20min |
| 2 | LLM 批量生成 30 篇 | `data/knowledge_base/` 扩展 | 2h |
| 3 | 人工抽查质量 | 审核通过率 > 90% | 30min |
| 4 | KnowledgeBase `ingest_directory()` 全量导入 | 重建索引 | 5min |
| 5 | 搜索命中率验证 | 对 10 个测试查询全命中 | 15min |
| 6 | 脚本化处理公开数据集（可选） | `scripts/import_dataset.py` | 2h |

---

## 更新日志

| 日期 | 操作 | 说明 |
|------|------|------|
| 2026-06-07 | 创建 | RAG + GREP 双轨知识检索方案初版 |
| 2026-06-07 | 新增 §10 | 知识库扩充策略（LLM 批量生成 + 公开数据集 + 自动化） |
