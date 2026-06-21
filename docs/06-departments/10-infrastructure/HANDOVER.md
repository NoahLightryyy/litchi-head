---
department: 基础设施部
codebase: src/utils/
last_updated: 2026-06-21
---

# ⚙️ 基础设施部工作交接

## 当前状态

### 模块完成度

| 子系统 | 状态 | 说明 |
|:-------|:----:|:------|
| LLMService（llm.py） | ✅ | DeepSeek/OpenAI/Anthropic 统一封装 + Streaming + LLMConfig |
| 配置管理（config.py） | ✅ | Pydantic Settings 环境变量加载 |
| 费用追踪（cost_tracker.py） | ✅ | Token 消耗 + 费用持久化 |
| 结构化日志（logger.py） | ✅ | 统一日志输出格式 |
| 复杂度路由（complexity_router.py） | ✅ | 简单/复杂任务自动路由 chat/reasoner |

### 测试

| 测试集 | 测试数 |
|:-------|:------:|
| llm.py 测试 | 12 |
| cost_tracker.py 测试 | 15 |
| 基础设施合计 | ~30 |

### 关键架构决策

- **单入口**：所有 LLM 调用必经 `LLMService`，禁止直调 ChatDeepSeek/ChatOpenAI
- **参数化**：LLMConfig 标准化 temperature/max_tokens，无硬编码
- **错误向上**：基础设施层不吞异常，抛给业务层处理
- **多 Provider**：DeepSeek 默认 → OpenAI 备选 → Anthropic 备选

---

## 开放债务

| ID | 描述 | 优先级 | 预估 |
|:---|:-----|:------:|:----:|
| TD-001 🔧 | LLM 封装层 — 核心完成，模型路由待补 | 🟡 | ~2.5h |
| TD-005 | 双配置源（settings.yaml + config.py）未协调 | 🟡 | 1h |
| TD-007 | ensure_dirs() 定义了从未被调用 | 🟢 | 10min |
| TD-008 | 模型价格硬编码在 cost_tracker.PRICES | 🟢 | 30min |
| TD-038 🔴 | `.env` 明文 API 密钥 | 🔴 | 30min |
| TD-040 | LLM Provider fallback 链（DeepSeek→OpenAI 自动降级） | 🟡 | 1d |
| TD-055 | TD-008 同源，价格硬编码重复登记 | 🟢 | — |

## 已关闭

| ID | 标题 | 修复日期 |
|:---|:-----|:--------|
| TD-009 | CI 迁移 GitHub Actions | 2026-06-06 |
| TD-011 | Pyright extraPaths 硬编码 | 2026-06-05 |
| TD-012 | LLM 参数硬编码 | 2026-06-07 |
| TD-013 | 缺少 streaming 接口 | 2026-06-08 |
| TD-015 | 缓存不支持多配置 | 2026-06-08 |

---

## 下一步优先级

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 🔴 | **TD-038 密钥管理** — 密钥轮换 + 凭据管理器 | 无 |
| 2 🟡 | TD-001 模型路由补完（简单/复杂自动路由） | 无 |
| 3 🟡 | TD-040 LLM Provider fallback 链 | 无 |
| 4 🟢 | TD-005/TD-007/TD-008 小修 | 无 |

---

## 关键文件索引

| 文件 | 行数 | 说明 |
|:-----|:----:|:------|
| `src/utils/llm.py` | 513 | LLMService 统一调用入口 |
| `src/utils/config.py` | — | Pydantic Settings 环境变量加载 |
| `src/utils/cost_tracker.py` | — | Token + 费用追踪 |
| `src/utils/logger.py` | — | 结构化日志 |
| `src/utils/complexity_router.py` | 303 | 模型自动路由 |
| `docs/06-departments/10-infrastructure/ROLE.md` | — | 👤 基础设施部角色定义 |
| `docs/06-departments/10-infrastructure/STANDARDS.md` | — | 📐 基础设施部技术规范 |
