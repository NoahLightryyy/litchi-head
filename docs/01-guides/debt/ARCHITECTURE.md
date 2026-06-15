# 🏛️ 架构设计债务

> 模块/组件拆分不合理、缺少抽象层、设计缺陷。

---

###### TD-001 缺少 LLM 调用封装层

| 属性 | 值 |
|------|-----|
| **分类** | `🏛️ design` `severity:critical` `module:utils` `impact:开发速度` |
| **发现日期** | 2026-06-05 |
| **状态** | `🔧 修复中` |
| **本金估算** | ∼4h |
| **实际工时** | ∼1.5h（核心实现完成） |

**描述**：
项目没有 `src/utils/llm.py`。这是整个平台的引擎，所有业务逻辑都依赖它。

**已修复项**：
1. ✅ `ChatDeepSeek` / `ChatOpenAI` 统一封装
2. ✅ `with_structured_output()` 结构化输出
3. ✅ 错误重试和指数退避（tenacity）
4. ✅ `cost_tracker.py` 集成
5. ✅ `langchain_anthropic` 惰性导入
6. ⬜ 模型路由（简单/复杂任务用不同模型）

---

###### TD-005 双配置源未协调

| 属性 | 值 |
|------|-----|
| **分类** | `🏛️ design` `severity:moderate` `module:utils` `impact:开发速度` |
| **发现日期** | 2026-06-05 |
| **状态** | `📋 已确认` |
| **本金估算** | ∼1h |

**描述**：
`config/settings.yaml` 和 `src/utils/config.py`（Pydantic Settings）两套配置系统部分重叠，无明确优先级。

**修复方向**：
统一优先级规则（`.env` → `Settings` 默认值 → `settings.yaml`），或统一为单源。

---

###### TD-017 缺少反思/学习闭环

| 属性 | 值 |
|------|-----|
| **分类** | `🏛️ design` `severity:critical` `module:debate+memory` `impact:产品竞争力` |
| **发现日期** | 2026-06-14 |
| **状态** | `📋 已确认` |
| **本金估算** | ∼2d（M2 交易后反思完整实现） |

**描述**：
9 层分析链路到 PM 裁决就结束了，没有"决策→实际收益→反思→进化"的闭环。竞品 TradingAgents（Decision Memory）、ContestTrade（竞赛排位）、EvoTraders（ReMe 轨迹学习）都有反思机制。

**修复方向**（M2 交易后反思）：
1. 短期：TradingAgents Decision Memory 模式 — 记录决策+实际收益+反思文本注入
2. 中期：EvoTraders ReMe 模式 — 完整执行轨迹+向量检索
3. 长期：ContestTrade 排位模式 — Agent 历史准确率追踪+动态权重
