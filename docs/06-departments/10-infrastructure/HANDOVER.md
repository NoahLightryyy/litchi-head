---
department: 基础设施部
codebase: src/utils/
last_updated: 2026-06-22 (DP-001 完成)
---

# ⚙️ 基础设施部工作交接

## 当前状态

### 模块完成度

| 子系统 | 状态 | 说明 |
|:-------|:----:|:------|
| LLMService（llm.py） | ✅ | DeepSeek 统一封装 + Streaming + LLMConfig（单 Provider 策略） |
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

- **单入口**：所有 LLM 调用必经 `LLMService`，禁止直调 `ChatDeepSeek`
- **参数化**：LLMConfig 标准化 temperature/max_tokens，无硬编码
- **错误向上**：基础设施层不吞异常，抛给业务层处理
- **单 Provider 策略**：只留 DeepSeek（chat + reasoner），`get_llm(provider=...)` 接口保留供未来扩展

---

## 开放债务

| ID | 描述 | 优先级 | 预估 |
|:---|:-----|:------:|:----:|
| TD-005 | 双配置源（settings.yaml + config.py）未协调 | 🟡 | 1h |
| TD-007 | ensure_dirs() 定义了从未被调用 | 🟢 | 10min |
| TD-008 | 模型价格硬编码在 cost_tracker.PRICES | 🟢 | 30min |
| TD-055 | TD-008 同源，价格硬编码重复登记 | 🟢 | — |

## 已关闭

| ID | 标题 | 修复日期 |
|:---|:-----|:--------|
| TD-009 | CI 迁移 GitHub Actions | 2026-06-06 |
| TD-011 | Pyright extraPaths 硬编码 | 2026-06-05 |
| TD-012 | LLM 参数硬编码 | 2026-06-07 |
| TD-013 | 缺少 streaming 接口 | 2026-06-08 |
| TD-015 | 缓存不支持多配置 | 2026-06-08 |
| TD-038 | `.env` 明文存储 API 密钥（Windows Credential Manager） | 2026-06-21 |
| TD-040 | ~~LLM Provider fallback 链~~ — 单 provider 策略，无需 fallback | 2026-06-22 |
| TD-001 | ~~多 provider 分支精简~~ — DP-001 模型瘦身完成（只留 deepseek） | 2026-06-22 |

---

## 下一步优先级

### 现有债务

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 🟡 | TD-005 双配置源协调 | 无 |
| 2 🟢 | TD-007/TD-008/TD-055 小修 | 无 |

### 设计哲学新任务（DP 系列）

> 基于 2026-06-22 设计哲学会议。完整背景见 [DESIGN_PHILOSOPHY.md](../../00-overview/DESIGN_PHILOSOPHY.md)。

| DP | 事项 | 状态 |
|:--:|:-----|:----:|
| **DP-001** 🥇 | **模型瘦身** — ✅ 已完成 | ✅ |


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
