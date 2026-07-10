# ADR-007: DeepSeek 作为主力 LLM

| 字段 | 值 |
|------|-----|
| **日期** | 2026-06-03 |
| **状态** | ✅ 已采纳（开发期） |
| **影响范围** | `src/utils/llm.py`, 成本 |

**上下文**：
API 成本控制对 MVP 阶段至关重要。

**决策**：
开发测试期默认使用 DeepSeek-Chat，保留 OpenAI 作为 fallback。
通过 `LLM_PROVIDER` 环境变量切换。

**成本对比**（单次辩论约 65k tokens）：

| 模型 | 单次成本 | 一个月开发（1000次） |
|------|---------|-------------------|
| DeepSeek-Chat | ~¥0.06 | ~¥60 |
| GPT-4o-mini | ~¥0.32 | ~¥320 |
| GPT-4o | ~¥1.92 | ~¥1,920 |
| Claude Sonnet 4 | ~¥1.07 | ~¥1,070 |

**理由**：
1. 成本仅为 GPT-4o 的 1/30
2. 中文金融场景表现足够
3. 保留 OpenAI API 作为 fallback

**后果**：
- ✅ 开发测试成本可控
- ⚠️ 最终上线可能需要切换到更强模型（需重新测试验证）

## 2026-07-10 补充：运行时收敛，接口开放

DP-001 后，Phase R 当前运行时默认收敛为 DeepSeek 单 Provider，以降低实盘加固阶段的配置复杂度。

但这不是永久放弃多模型架构。用户明确要求：未来 Agent 系统的模型接口需要保留多样性，方便接入不同模型，以获得不同 Agent 效果。

因此 ADR-007 的当前解释为：

- **默认运行时**：DeepSeek 优先，当前不主动恢复复杂 fallback 链。
- **接口契约**：继续保持 `LLMService` / `LLMConfig` 抽象，不允许业务 Agent 直连具体模型 SDK。
- **未来扩展**：允许按 Agent/任务接入 OpenAI、Claude、Qwen、本地模型等不同 Provider。

详见：`docs/99-archive/MODEL-INTERFACE-DIVERSITY.md`。
