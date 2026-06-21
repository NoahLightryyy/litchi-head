---
department: AI Agent 架构部
codebase: src/agents/ + src/core/
last_updated: 2026-06-21
---

# 🤖 AI Agent 架构部工作交接

## 当前状态

### 模块完成度

| 子系统 | 状态 | 说明 |
|:-------|:----:|:------|
| BaseAgent 基类 | ✅ | AgentContext + AgentResult[Generic[T]] |
| MasterAgent 通用化 | ✅ | Skill 插件盘 + KB + LLM + 结构化输出 |
| XiaoZhiAgent 教育问答 | ✅ | RAG + LLM 问答 |
| 通信协议（protocol.py） | ✅ | AgentMessage + MessageRouter |
| AGENT_REGISTRY 注册 | ✅ | 所有 Agent 在此注册 |

### 测试

| 测试集 | 测试数 |
|:-------|:------:|
| Agent 基类测试 | 15+ |
| MasterAgent 系列测试 | 174 |
| 通信协议测试 | 20 |
| **Agent 模块合计** | **~200+** |

### 关键架构决策

- **AgentResult 泛型化**：`AgentResult[T]` 支持类型化输出，Pyright 可静态校验
- **向后兼容**：旧版 `AgentResult(data=dict)` 仍可用，新代码推荐泛型
- **MasterAgent 通用化**：同一个 Agent 骨架 + 不同人格定义 = 7 位投资大师

---

## 开放债务

| ID | 描述 | 优先级 | 预估 |
|:---|:-----|:------:|:----:|
| TD-003 | MessageRouter 纯内存存储，进程重启丢失 | 🟡 | 1h |
| TD-006 | EvidenceItem 无校验逻辑 | 🟢 | 30min |
| TD-050 | XiaoZhiAgent 无 LLM 错误路径测试 | 🟡 | 30min |

---

## 下一步优先级

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 🟡 | TD-003 MessageRouter 持久化（`save_snapshot/load_snapshot`） | 无 |
| 2 🟡 | TD-050 XiaoZhiAgent 补 LLM 超时/异常/非法返回测试 | 无 |
| 3 🟢 | TD-006 EvidenceItem 添加 `validate_chain()` 方法 | 无 |

---

## 关键文件索引

| 文件 | 行数 | 说明 |
|:-----|:----:|:------|
| `src/agents/base.py` | 140 | Agent 基类 + AgentResult 泛型 |
| `src/agents/master_agent.py` | 232 | MasterAgent 通用实现（Skill+KB+LLM） |
| `src/agents/xiao_zhi.py` | — | 教育问答 Agent |
| `src/core/protocol.py` | — | 通信协议（MessageRouter, AgentMessage） |
| `docs/06-departments/03-ai-agents/ROLE.md` | — | 👤 AI Agent 架构部角色定义 |
| `docs/06-departments/03-ai-agents/STANDARDS.md` | — | 📐 AI Agent 架构部技术规范 |
