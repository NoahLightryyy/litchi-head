# ⚙️ 基础设施债务

> CI/CD、部署、项目配置相关缺陷。

---

###### TD-019 强依赖单一 LLM 提供商

| 属性 | 值 |
|------|-----|
| **分类** | `⚙️ infrastructure` `severity:moderate` `module:utils` `impact:运行时稳定` |
| **发现日期** | 2026-06-14 |
| **状态** | `📋 已确认` |
| **本金估算** | ∼0.5d |

**描述**：
LLMService 架构上支持多 provider，但所有测试只在 DeepSeek 上验证过。竞品支持 7-13 种 LLM。

**修复方向**：
1. 补充 Ollama 本地模型集成测试
2. 验证 anthropic provider 集成测试
3. 增加 provider fallback 链
