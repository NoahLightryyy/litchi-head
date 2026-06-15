# 功能模块：Agent 编排 — 调研分析

> 本文档记录该模块在行业中的竞争格局、竞品分析、架构对比等调研信息。
> 是 [SPEC.md](SPEC.md) 设计决策的背景依据，不是实现规格。

## 所属战线

### 多 Agent 辩论决策（底层支撑层）

> 编排不属于独立战线，而是**辩论决策战线的底层基础设施**——Agent 怎么起床、怎么排队、怎么传递消息，都由编排层决定。
>
> [查看战线完整分析](../../99-archive/KNOWLEDGE_BASE.md#-战线-1多-agent-辩论决策)

### 在这个战场中的角色

```
多Agent辩论决策（上层）     ← 编排层服务于此
    ↑
Agent 编排层（你在的地方）  ← 决定Agent调度、并行/串行、状态传递
    ↑
LangGraph / 自定义框架     ← 编排的技术载体
```

每个辩论决策项目的背后都有一套编排系统：
- **TradingAgents** → LangGraph StateGraph（4层递进，DAG 有向无环图）
- **AI Hedge Fund** → 自定义 Pipeline + React Flow（可视化节点编排）
- **RD-Agent** → 自定义 R&D 双循环编排（R-Agent → D-Agent 循环）
- **AI-Trader** → 自定义 Agent 原生编排（动态注册 Agent 协议）
- **你** → LangGraph StateGraph（当前 D→D→A 线性流程）

## 竞品分析

### 行业参照项目

| 项目 | 编排方式 | 值得看的 | 和你的对比 |
|------|---------|---------|-----------|
| **TradingAgents** | LangGraph StateGraph（4层递进+并行+串行混合） | 多层编排设计、条件路由、Checkpoint/Resume | 你的流程更短（D→D→A），他们更多层 |
| **AI Hedge Fund** | 自定义 Pipeline（19个并行 → PM综合） | React Flow 可视化工作流编辑 | 可视化的思路值得借鉴 |
| **RD-Agent** | 自定义 R&D 双循环（R→D→验证→反馈→R） | "循环"不是"流水线"的设计 | 适合未来的策略进化场景 |
| **AI-Trader** | 自定义 Agent 原生（动态注册协议） | 一条消息加入新Agent | 你的未来 Skill/人格市场可参考 |

### 关键启示

1. **TradingAgents** 不会把所有 Agent 的上下文拼在一起，而是**通过 StateGraph 在节点间传递结构化数据**。每个 Agent 只看到它需要的信息。
2. 可视化编排（AI Hedge Fund 的 React Flow）在调试和展示层有借鉴价值。
3. 循环式编排（RD-Agent）在策略自进化场景优于流水线式编排。

## 架构对比分析

### 你现在的编排（线性 D→D→A）

```
collect_data ──→ master_round ──→ aggregate ──→ END
                    │
              顺序调大师（避开了并行写入冲突）
```

特点：目前是**单线顺序**，简单稳定，但浪费了并行能力。

### TradingAgents 的编排（4层混合编排）

```
分析师层（并行）──→ 研究员层（串行）──→ 交易员（串行）──→ 风控层（并行）──→ PM（串行）

分析师1 ──┐
分析师2 ──┤         Bull ──┐
分析师3 ──┤ 并行       │   串行(2轮)     Trader ──┐    激进 ──┐
分析师4 ──┘         Bear ──┘                       │    中性 ──┤ 并行 → PM
                                                   │    保守 ──┘
                                            ┌──────┘
                                            │  每个Agent有独立的工具集和角色提示词
                                            │  Agent互相不共享上下文
                                            │  只通过StateGraph传递结构化数据
```

**关键设计**：TradingAgents 不会把所有 Agent 的上下文拼在一起，而是**通过 StateGraph 在节点间传递结构化数据**。每个 Agent 只看到它需要的信息。

### RD-Agent 的编排（R&D 双循环）

```
不是"流水线"，是"循环"：
  R-Agent(研究) → 假设 → D-Agent(开发) → 实现+回测 → 结果分析 → 反馈 → R-Agent(下一轮)
                                                                         ↑
                                                                    自进化循环
```

### AI-Trader 的动态注册（未来方向）

```
Agent 不固定，通过注册协议动态加入：
  "我想加入交易生态" → 发一条消息 → 系统为其注册能力接口 → 立即生效
```

## 研究问题

### 当前阶段
- [ ] LangGraph StateGraph vs 自定义编排器：当前线性流程下，StateGraph 是否 overkill？
- [ ] 并行执行时 State 写入冲突怎么彻底解决？（目前用顺序调用绕开了）
- [ ] Checkpoint/Resume 需要吗？什么时候需要？

### 扩展阶段
- [ ] 未来 Agent 数量扩展到 20+ 时，编排复杂度怎么控制？
- [ ] 条件路由：什么情况下跳过某些 Agent？（例如没有新闻时跳过新闻分析）
- [ ] Agent 注册表设计：新 Agent 加入需不需要改 Graph 定义？还是配置化？

### 架构对比
- [ ] TradingAgents 的"通过 State 传递结构化数据" vs 你的"所有 Agent 共享上下文"，各有什么优劣？
- [ ] RD-Agent 的"循环"编排 vs 你的"流水线"编排，哪个更适合策略进化？

## 子文件夹索引

| 路径 | 用途 |
|------|------|
| `./LangGraph实践/` | StateGraph 的使用技巧、踩坑记录、最佳实践 |
| `./TradingAgents编排分析/` | TradingAgents 的多层 StateGraph 源码分析 |
| `./并行策略研究/` | Agent 并行执行方案、冲突解决、性能调优 |
| `./动态注册机制/` | AI-Trader 动态 Agent 注册的源码分析 + 适应性设计 |

> 注：以上子文件夹为按主题组织的调研笔记目录（docs 重组时规划），尚未物理创建。

## 深挖方向建议

**优先级 1**：解决 LangGraph 并行写入冲突的问题。你目前用顺序调用绕开了，但可以想想真正并行化的方案（例如每个 Agent 写自己的 state 字段，不共享冲突）。

**优先级 2**：研究 TradingAgents 的多层 StateGraph 设计（分析师并行→辩论串行→风控并行→PM串行），和你的 D→D→A 流程对比，看哪些层可以复用。

**优先级 3**：设计 Agent 注册表（为 Phase 2 的 Skill/人格市场做准备）。目标是：加一个新 Agent 不改 Graph 定义，只改配置文件。

> **最后更新**：2026-06-15（从 SPEC.md 拆分）
