# litchi-head — AI 项目指令

> 多智能体投资决策平台（LangGraph + DeepSeek）
> 当前阶段：Phase 1 MVP 期（data → debate 接驳完成）

---

## 核心规则

1. **会话启动**：执行 `/resume-session` Skill（项目级），或手动读取 `docs/流程规范/AI会话交接文档.md` §2+§5 + 最新工作日志
2. **三同步原则**：代码 + 文档 + 债务日志，改一个必须改全部
3. **发现债务必登记** — 使用 `docs/技术债务与架构决策/债务新增模板.md` 模板
4. **每次会话结束必须更新**：AI 工作日志 + 债务日志（如有变更）
5. **模型策略**：日常用 `deepseek-chat`（快速，无思考），复杂任务才切 `deepseek-v4-pro`（推理）。见下方「模型策略」节。

## 技术栈关键约定

- **Pydantic** `BaseModel` — 所有模块间数据传输（见 ADR-001）
- **LangGraph** `StateGraph` — Agent 编排（见 ADR-002）
- **DeepSeek-Chat** — 主力 LLM，OpenAI 为 fallback（见 ADR-007）
- **类型注解必须完整** — Pyright basic mode 零错误通过
- **`src/utils/llm.py`** — 所有 LLM 调用必经此层，不得直接实例化 ChatDeepSeek

## 项目文档索引

| 文档 | 位置 |
|------|------|
| AI 工作流程 | `docs/流程规范/AI自动化工作流程.md` |
| 当前工作日志 | `docs/ai-work-logs/` |
| 技术债务日志 | `docs/技术债务与架构决策/技术债务日志.md` |
| 债务新增模板 | `docs/技术债务与架构决策/债务新增模板.md` |
| 架构决策记录 | `docs/技术债务与架构决策/架构决策记录.md` |
| 设计文档 | `docs/架构设计/` · `docs/产品需求/` · `docs/调研分析/` |
| 环境变量配置 | `docs/环境配置指南.md`（配置变更时参考） |

## 模型策略（快慢分离）

| 模型 | 定位 | 思考模式 | 适用场景 |
|------|------|:---:|------|
| `deepseek-chat` | **默认**（日常开发） | ❌ 无 | 代码编辑、Git、文件读写、简单问答、文档更新 |
| `deepseek-v4-pro` | 按需切换（复杂任务） | ✅ 推理 | 架构设计、根因分析、复杂重构、安全审查、多模块影响评估 |

```bash
# 日常开发（Windows 用户环境变量，默认值）
ANTHROPIC_MODEL=deepseek-chat

# 遇到复杂任务时，临时改为 deepseek-v4-pro，重启 Claude Code
```

> **原则**：规则和 Skill 越多，越需要关闭默认思考——推理模型会穷举遍历所有规则的交叉影响，即使任务只涉及其中一个。

## 快速命令

```bash
make install   # 安装依赖
make check     # 一键检查（lint + type + test）
make lint      # Ruff 代码风格
make type      # Pyright 类型检查
make test      # Pytest 测试

# Docker 开发环境
make docker-build   # 构建开发镜像
make docker-test    # 在容器中跑测试
make docker-check   # 在容器中全量检查
make docker-shell   # 进入容器 bash
```
