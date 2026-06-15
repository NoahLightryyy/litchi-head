# 📖 术语表

## 项目核心概念

| 术语 | 说明 |
|:-----|:-----|
| **大师（Master）** | 对应一种投资风格的 AI Agent，如价值派、趋势派、情绪派等 |
| **辩论（Debate）** | 多位大师对同一标的进行分析、交叉审阅、反驳的过程 |
| **评审（Review）** | 独立 LLM Agent 阅读所有大师分析后输出结构化裁决报告 |
| **投票汇总（Aggregate）** | 对大师评分进行加权汇总，输出最终投资建议 |
| **方向约束（Direction）** | 强制每位大师输出 Bullish/Bearish/Neutral 方向判断 |

## 模块

| 术语 | 说明 |
|:-----|:-----|
| **Data Collector** | 数据采集模块，封装 akshare 调用 |
| **Debate Engine** | 辩论决策引擎，核心编排流程 |
| **Memory Store** | 记忆存储系统，命名空间隔离 |
| **Agent Orchestrator** | Agent 编排器，LangGraph StateGraph |
| **Master Agent** | 通用大师 Agent，通过配置控制行为 |
| **Risk Manager** | 风控模块（预留） |
| **Trade Execution** | 交易执行模块（预留） |

## 技术

| 术语 | 说明 |
|:-----|:-----|
| **LangGraph** | Agent 编排框架，StateGraph 驱动工作流 |
| **Pydantic** | 全栈数据校验层，所有模块间数据传输使用 |
| **DeepSeek** | 主力 LLM 模型（deepseek-chat 日常 / v4-pro 复杂任务） |
| **akshare** | 免费 A 股数据源 |
| **StateGraph** | LangGraph 的状态图，节点=Agent，边=消息传递 |
| **AgentResult[T]** | 泛型 Agent 输出，T 为具体 Pydantic 输出模型 |

## 架构决策

| 术语 | 说明 |
|:-----|:-----|
| **ADR** | Architecture Decision Record，架构决策记录 |
| **TD** | Technical Debt，技术债务 |
| **Namespace Memory** | 命名空间记忆：`(memory_type, agent_role, user_id)` |
| **Provider 模式** | 数据源抽象层，切换数据源不改业务代码 |
