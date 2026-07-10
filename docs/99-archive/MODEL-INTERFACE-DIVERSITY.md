# Agent 模型接口多样性战略

> **一句话**：运行时可以阶段性收敛到 DeepSeek，但 Agent 系统的模型接口必须保持可插拔，未来允许不同 Agent 接入不同模型以获得差异化效果。

## 背景

2026-06-22 的 DP-001 做了“模型瘦身”：删除运行时多 Provider 分支，当前产品默认只保留 DeepSeek，以降低成本、减少配置复杂度、提升开发稳定性。

2026-07-10 用户进一步澄清：未来 Agent 系统里的模型接口肯定要保留多样性，方便接入不同模型，获得不同效果。

这两件事不冲突：

- **短期运行策略**：DeepSeek 单 Provider，降低实盘加固阶段的复杂度。
- **长期接口策略**：Agent 与 LLMService 的契约不能写死到某一个模型，保留未来多模型插拔空间。

## 决策

Agent 系统采用“运行时收敛、接口开放”的策略：

1. **当前默认模型仍是 DeepSeek**
   - 产品内所有 LLM 调用继续走 `src/utils/llm.py`。
   - Phase R 阶段不重新引入复杂 fallback 链，避免增加实盘加固噪声。

2. **接口层保留模型多样性**
   - `LLMConfig`、`LLMService`、Agent 调用点应保持模型参数化。
   - 不允许业务 Agent 直接实例化 `ChatDeepSeek` 或任何具体模型 SDK。
   - 不把 prompt、输出解析、错误处理写死到单一模型的特殊行为上。

3. **未来支持按 Agent/任务选择模型**
   - 稳健分析型 Agent 可用低温、低成本模型。
   - 反共识/灵感型 Agent 可用更高随机性或更擅长发散的模型。
   - 审计/校验型 Agent 可使用与主分析不同的模型，降低同源偏差。
   - 本地模型、OpenAI、Claude、Qwen、DeepSeek 等都应能通过统一接口接入。

4. **多模型不是马上做**
   - Phase R 优先级仍是结果闭环、置信度量化、数据真实性和复盘看板。
   - 多模型扩展属于架构保留点，只有在明确收益大于复杂度时再落地。

## 设计原则

| 原则 | 含义 |
|------|------|
| 单入口 | 所有模型调用必须经过 `src/utils/llm.py` |
| 可替换 | Agent 不依赖具体 SDK，只依赖项目内部抽象 |
| 可比较 | 不同模型输出应能落到同一 Pydantic 契约中，方便评估 |
| 可观测 | 每次调用记录模型名、配置、token、成本、错误 |
| 可回退 | 多模型恢复时，失败路径必须显式暴露，不静默吞错 |

## 与 DP-001 的关系

DP-001 是运行时复杂度治理，不是永久放弃多模型架构。

更准确的表述是：

> 当前产品运行时默认 DeepSeek 单 Provider；Agent/LLM 接口保留未来多模型插拔能力。

## 后续触发条件

以下任一情况出现时，可以重新评估多模型接入：

- DeepSeek 在关键任务上稳定性或质量不足
- 需要独立模型做交叉校验，降低同源幻觉
- 某类 Agent 明显适合不同模型风格
- 成本、延迟、合规或本地部署需求发生变化
- 交易复盘数据证明某模型组合优于单模型

## 关联文件

- `src/utils/llm.py`
- `src/utils/complexity_router.py`
- `docs/05-decisions/ADR-007-deepseek.md`
- `docs/06-departments/10-infrastructure/HANDOVER.md`
- `docs/01-guides/workflow/DEVELOPMENT.md`
