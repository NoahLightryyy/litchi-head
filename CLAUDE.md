# litchi-head — AI 项目指令

> 多智能体投资决策平台（LangGraph + DeepSeek）
> 当前阶段：Phase 0 基建期

---

## 核心规则

1. **必须遵守** `docs/流程规范/AI自动化工作流程.md` — 每次会话的标准操作流程
   - 新会话启动时：按 §2.1 **优化后的三层流程**执行
   - memory 已自动注入身份卡/ADR/当前状态，不需要我再读文档清单
2. **三同步原则**：代码 + 文档 + 债务日志，改一个必须改全部
3. **发现债务必登记** — 使用 `docs/技术债务与架构决策/债务新增模板.md` 模板
4. **每次会话结束必须更新**：
   - AI 工作日志 `docs/ai-work-logs/`
   - 债务日志（如有新增/变更）
5. **复杂任务启用 deepseek 推理** — 见 memory 中 `use-deepseek-reasoning.md`

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

## 快速命令

```bash
make install   # 安装依赖
make check     # 一键检查（lint + type + test）
make lint      # Ruff 代码风格
make type      # Pyright 类型检查
make test      # Pytest 测试

# Windows PowerShell
.\scripts\check.ps1
```
