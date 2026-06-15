# ADR-010: Agent 运行时增强 — LLMConfig / streaming / 辩论上下文

| 字段 | 值 |
|------|-----|
| **日期** | 2026-06-07 |
| **状态** | ✅ 已采纳 |
| **影响范围** | `src/utils/llm.py`, `src/agents/base.py`, `src/core/protocol.py` |

**上下文**：
2026-06-07 全面项目审查发现 4 处骨骼级缺陷，必须在 Phase 0 修复：
1. LLM 参数硬编码 — `temperature=0.3` 不可按 Agent 覆盖
2. 缺少 streaming 接口 — `astream()` 未定义
3. AgentContext 无辩论槽位 — `peer_outputs`/`current_round`/`target_audience`
4. LLM 实例缓存不支持多配置 — 不同 temperature 互相覆盖

**决策**：
1. 引入 `LLMConfig` frozen dataclass（temperature/max_tokens/model/stream/reasoning_effort）
2. `AgentContext` 新增 `peer_outputs`/`current_round`/`target_audience`（默认向后兼容）
3. LLM 缓存键扩展：默认配置按 provider 缓存，非默认不缓存
4. 新增 `astream()` 流式接口

**核心代码变更**：
```python
@dataclass(frozen=True)
class LLMConfig:
    temperature: float = 0.3
    max_tokens: int = 8192
    model: str | None = None
    stream: bool = False
    reasoning_effort: str | None = None
```

**向后兼容性**：
- `LLMConfig()` 默认值与当前硬编码值完全相同
- 所有现有调用传 `None` 则行为不变
- 173 个现有测试零回归

**后果**：
- ✅ Agent 接口在 Q&A 和辩论两种模式中复用同一套签名
- ✅ 辩论引擎写的时候不需要回来改 Agent 的 `run()` 接口
- ✅ streaming UI 需要时 `llm_service.astream()` 可直接衔接
- ⚠️ `LLMConfig` 引入新配置对象，但 `None=默认值` 策略使复杂度最低

**修复的债务**：TD-012 / TD-013 / TD-014 / TD-015
