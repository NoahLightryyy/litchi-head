# 功能模块：记忆与反思 — 调研分析

> 本文档记录该模块在行业中的竞争格局、竞品分析、架构对比等调研信息。
> 是 SPEC.md 设计决策的背景依据，不是实现规格。

## 所属战线

**自进化/反思系统**战线格局：

```
                    ┌── 完整反思系统路线 ── EvoTraders ReMe
                    │    阿里巴巴通义实验室出品。三阶段循环：
                    │    经验提取 → 上下文适配重用 → 效用驱动精炼
                    │    论文 ArXiv 2512.10696，Qwen3-32B +15pp 提升
                    │
  自进化/反思系统 ──┼── 轻量决策记忆路线 ── TradingAgents
                    │    trading_memory.md 纯文本记录历史决策+收益
                    │    下次自动注入 prompt，实现简单但有效
                    │
                    └── 技术缓存路线 ── Qlib
                         多级缓存（LRU+Redis），和"反思"无关
                         只是数据层面的加速，非智能层面的自进化
```

你的位置：当前在 **技术缓存路线**（JsonFileStore key-value 存储），向**反思系统路线**进化。`src/memory/` 已有基础存储设施，但缺少"反思→学习→进化"闭环。

## 竞品分析

| 项目 | ⭐ | 战线角色 | 值得看的 |
|------|-----|---------|---------|
| **EvoTraders ReMe** | — | 战线领头羊 | 三阶段循环（提取→重用→精炼）、评分优先检索、跨交易日进化 |
| **TradingAgents** | 71k | 轻量路线 | `trading_memory.md` 纯文本记录+自动注入 prompt |
| **Qlib** | 36k | 技术缓存路线 | MemCache(LRU) + 表达式缓存 + 数据集缓存 + Redis |

### 关键启示

| 来自谁 | 启示 |
|--------|------|
| **EvoTraders ReMe** | 三阶段循环、评分优先检索、跨交易日持续学习——这是"自进化"的标准答案 |
| **TradingAgents** | 轻量起步方案——用纯文本记录决策+收益，不要等复杂系统 |
| **Qlib** | 当你的记忆库数据量大了以后，多级缓存的思路值得参考 |

## 架构对比分析

### EvoTraders ReMe 的做法（目标方案）

```
┌──────────────────────────────────────────────────────────┐
│  三阶段自进化循环                                          │
│                                                          │
│  Phase 1: 经验提取                                        │
│    ├─ 交易完成后, 多维分析执行轨迹                         │
│    │   (成功的模式识别 + 失败分析 + 对比洞察)              │
│    ├─ LLM-as-a-Judge 验证后存入记忆池                     │
│    └─ 评分：盈利日 1.0，亏损日 0.0，优先检索高分经验       │
│                                                          │
│  Phase 2: 上下文适配重用                                   │
│    ├─ 通过场景感知索引（usage scenario）检索相关经验      │
│    ├─ 不是简单基于原始查询匹配                             │
│    └─ 检索到的经验注入到决策 Agent 的 context              │
│                                                          │
│  Phase 3: 效用驱动精炼                                     │
│    ├─ 自主添加有效记忆                                    │
│    ├─ 剔除过时或无效内容                                   │
│    └─ 形成闭环进化                                        │
└──────────────────────────────────────────────────────────┘

每日交易六阶段：
  Phase 0: 清空短期记忆
  Phase 1-4: 正常分析+决策+交易
  Phase 5: 反思 → 计算实际盈亏 → 存入 ReMe
```

### TradingAgents 的轻量方案（起步参考）

```
trading_memory.md:
─────────────────────────────────────────
# Decision Memory for AAPL

| Date | Signal | Size | Return | Reflection |
|------|--------|------|--------|------------|
| 2026-01-05 | BUY | 0.3 | +2.1% | Good entry, momentum confirmed |
| 2026-01-12 | HOLD | 0.0 | -0.5% | OK, no action needed |
| 2026-01-20 | SELL | -0.2 | +1.8% | Early exit, missed further upside |

下次运行时，自动读入 → 注入 prompt → "历史记录显示上次卖出后股价继续上涨了1.8%"
```

## 研究问题

### M1 — 历史决策注入
- [x] **TradingAgents 做法**：`get_past_context()` 在 `propagate()` 开始时自动拉取同 ticker 最近 5 条 + 其他 ticker 最近 3 条，直接注入到 Agent 初始 prompt。
- [ ] 你的 `MemoryManager` 是否在 MasterAgent/Debate 启动时注入历史决策？
- [ ] TradingAgents 用纯文本注入（一个 markdown 文件），你用 `MemoryManager.search(namespace, query)` 是否有等价能力？
- [x] **结论**：你的 MemoryStore 基础设施比 TradingAgents 更先进（结构化 namespace 存储），但缺少"Agent 自动接入"这一层——Manager 的 `get_past_context()` 方法需要实现。

### M2 — 事后反思机制
- [x] **TradingAgents 做法**：`propagate()` 结束时存 `[pending]` 状态，下次同 ticker 运行时拉实际收益，补写 `REFLECTION:` 章节。
- [ ] 你的反思触发机制（事后补写）和 TradingAgents 的两阶段写入是否适合你的流程？
- [ ] 反思的分析维度：TradingAgents 只做 `reflect_on_final_decision(result, raw_return, alpha_return)`，你希望更丰富（决策质量→执行偏差→情绪影响）吗？
- [ ] 你的 `MemoryManager` 是否有"更新已存记录"的能力？（目前 JsonFileStore 是 put = 覆盖，可以满足）

### 存储层
- [ ] JSON 文件存储到什么时候需要升级？瓶颈在哪？
- [ ] 向量数据库 vs SQLite vs JSON：不同阶段的选型依据？
- [x] **TradingAgents 的做法**：纯文本 markdown 文件，append-only，max_entries 限制上限。连 JSON 都不用——说明轻量方案已足够 Phase 1 使用。

## 子文件夹索引

| 路径 | 用途 |
|------|------|
| `./存储方案对比/` | JSON / SQLite / 向量数据库 的选型分析（含 TradingAgents 纯文本方案对比） |
| `./反思机制设计/` | 交易后反思的触发时机、分析维度、存储格式 |
| `./EvoTraders_ReMe分析/` | ReMe 论文 + 源码阅读笔记 |
| `./记忆注入策略/` | 记忆如何注入 LLM context（prompt 拼接 vs RAG） |
| `./TradingAgents记忆分析/` | TradingAgents `trading_memory.md` 纯文本日志机制分析 |

## 深挖方向建议

> **核心发现**：你的 MemoryStore（JsonFileStore + namespace）比 TradingAgents 的纯文本 markdown 存储更先进。

### 优先：M1 — 历史决策注入到 Agent（记忆模块 ↔ 辩论模块）
**来源**：TradingAgents `get_past_context()` | **工作量**：中 | **影响范围**：`memory/manager.py` + `debate/orchestrator.py`

- 在 MemoryManager 中实现 `get_past_context(ticker, n_same=5, n_cross=3)` 方法
- 在 DebateOrchestrator 的 `collect_data` 步骤后，注入同 ticker 历史决策到 agent 的 prompt
- 简单起步：不向量检索，按 namespace + ticker 过滤取最新几条

> 注：M1 已在当前版本中完成实现并接入辩论编排器。此处保留原始调研记录供参考。

### 次优先：M2 — 事后反思机制
**来源**：TradingAgents `store_decision()` + `batch_update_with_outcomes()` | **工作量**：中 | **影响范围**：`memory/manager.py`

- 每次辩论结束时，调用 `MemoryManager.store_decision(ticker, decision)` 存为 pending
- 下次跑同 ticker 时，调用 `MemoryManager.resolve_pending(ticker)` 补写反思
- 注意：反思依赖端到端链路跑通（需要知道真实盈亏）

### 未来：存储层升级
- TradingAgents 的纯文本方案证明：Phase 1 根本不需要向量数据库
- 存储方案升级（JSON→SQLite→向量数据库）应在记忆量 > 500 条时再评估

> **最后更新**：2026-06-15（从 SPEC.md 拆分）
