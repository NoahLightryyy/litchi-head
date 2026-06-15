# 🛠️ 技术栈

## 核心运行时

| 层 | 技术 | 版本 | 说明 |
|:---|:-----|:----|:-----|
| 语言 | Python | 3.12+ | 主力开发语言 |
| 编排 | LangGraph | — | Agent 工作流编排（StateGraph） |
| 数据契约 | Pydantic | 2.x | 全栈数据校验（ADR-001） |
| 主力 LLM | DeepSeek | deepseek-chat / v4-pro | 快慢分离策略（ADR-007） |
| Fallback LLM | OpenAI | GPT-4o-mini / GPT-4o | 降级备选 |

## 数据层

| 组件 | 技术 | 说明 |
|:-----|:-----|:-----|
| A 股数据 | akshare | MVP 阶段唯一数据源（ADR-003） |
| 记忆存储 | JSON 文件 | MVP 阶段使用 JsonFileStore（ADR-011） |
| 缓存 | 内存 TTL | DataCollector 内置 |

## 前端（MVP）

| 组件 | 技术 | 说明 |
|:-----|:-----|:-----|
| 框架 | Streamlit | Phase 1 MVP 前端（ADR-004） |
| 图表 | Plotly | 金融图表渲染 |
| 未来 | React/Next.js | Phase 2 迁移目标 |

## 基础设施

| 组件 | 技术 | 说明 |
|:-----|:-----|:-----|
| 版本控制 | Git + GitHub | 远程仓库 |
| CI/CD | GitHub Actions | Ruff + Pyright + Pytest |
| 容器 | Docker | 开发环境容器化 |
| 包管理 | pip + requirements.txt | 依赖管理 |

## 模型策略（快慢分离）

| 模型 | 定位 | 思考模式 | 适用场景 |
|:-----|:-----|:--------:|:---------|
| `deepseek-chat` | 默认（日常开发） | ❌ 无 | 代码编辑、Git、简单问答 |
| `deepseek-v4-pro` | 按需切换（复杂任务） | ✅ 推理 | 架构设计、根因分析、多模块影响评估 |

**核心原则**：日常用 `deepseek-chat` 快速迭代，遇到复杂任务时才切 `v4-pro`。
