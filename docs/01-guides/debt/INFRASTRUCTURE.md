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

---

###### TD-038 `.env` 文件明文存储真实 API 密钥

| 属性 | 值 |
|------|-----|
| **分类** | `⚙️ infrastructure` `severity:critical` `module:all` `impact:安全` |
| **发现日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼30min |
| **日利息** | 密钥泄露可导致 AI 被恶意调用产生巨额费用 |
| **实盘影响** | 🔴 API 密钥泄露 → 被滥用 → 产生不合理账单 → 服务中断 |
| **触发场景** | OneDrive 同步、备份、git add --force、临时截图分享屏幕 |
| **用户能发现吗** | ❌ 不能 — 直到收到天价 API 账单或密钥被吊销 |

**描述**：
`.env` 文件包含真实且有效的 DEEPSEEK_API_KEY 和 ANTHROPIC_API_KEY，以明文形式存储在文件系统中。虽然被 `.gitignore` 忽略，但可能通过 Windows 搜索索引、OneDrive 同步、共享桌面、错误使用 `git add --force` 等途径泄露。

**具体问题**：
1. ❌ DEEPSEEK_API_KEY 明文
2. ❌ ANTHROPIC_API_KEY 明文（同时在 ANTHROPIC_AUTH_TOKEN 重复暴露）

**修复方向**：
1. **立即**：轮换这两个 API 密钥
2. **短期**：移至 Windows 凭据管理器或加密 secrets 文件
3. **长期**：考虑使用 vault/1Password CLI 集成

---

###### TD-039 无 API 速率限制（特别是 `/api/debate/run` 可被无限调用刷 AI 费用）

| 属性 | 值 |
|------|-----|
| **分类** | `⚙️ infrastructure` `severity:moderate` `module:backend` `impact:运行时成本` |
| **发现日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼1h |
| **实盘影响** | 🟡 `/api/debate/run` 每次触发 15 次 LLM 调用，无限制时几分钟内产生数百元 AI 费用 |
| **触发场景** | 恶意脚本或用户高频点击"开始辩论" |
| **用户能发现吗** | ❌ 不能 — 直到收到 API 账单 |

**描述**：
后端 14 个 API 端点完全开放，无认证、无速率限制。`/api/debate/run` 端点单次调用触发约 15 次 LLM API 调用，无限制即可被刷巨额费用。

**修复方向**：
1. 使用 `slowapi` 库添加全局速率限制
2. `/api/debate/run` 特别限制（如每分钟 2 次）
3. 本地环境使用 API key 简单认证

---

###### TD-040 LLM Provider fallback 链缺失

| 属性 | 值 |
|------|-----|
| **分类** | `⚙️ infrastructure` `severity:moderate` `module:utils` `impact:运行时稳定` |
| **发现日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼1d |
| **实盘影响** | 🟡 DeepSeek API 宕机时，整个辩论/交易/风控系统全部瘫痪，无自动降级 |
| **触发场景** | DeepSeek 服务不可用时（已出现过） |
| **用户能发现吗** | ✅ 能 — 全部 AI 功能挂掉，前端显示错误，但不知道是 LLM provider 问题 |

**描述**：
`src/utils/llm.py` 架构上支持多 provider，但 `_build_llm()` 只返回一个 provider 实例。DeepSeek 挂了不会自动切到 OpenAI，所有 LLM 调用直接抛异常。

**修复方向**：
1. 添加 provider fallback 链：DeepSeek → OpenAI → 报错
2. 每个 provider 调用失败时自动尝试下一个
3. 日志记录 fallback 切换事件

---

###### TD-041 数据新鲜度标注缺失

| 属性 | 值 |
|------|-----|
| **分类** | `⚙️ infrastructure` `severity:moderate` `module:data` `impact:可观测性` |
| **发现日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼2h |
| **实盘影响** | 🟡 用户不能判断看到的 K 线/行情是不是最新的 |
| **触发场景** | 缓存过期、数据源延迟、盘中查看历史数据 |
| **用户能发现吗** | ❌ 不能 — 数据看起来正常但可能已经过期 10 分钟 |

**描述**：
KLine 和 StockQuote 模型没有 `collected_at` 时间戳字段。前端无法展示"数据采集时间"，用户无法判断数据的新鲜度。`DataCollector` 的缓存元数据中 `"cached": false` 被硬编码为 false，即使数据来自缓存也不标注。

**具体问题**：
1. ❌ `src/data/models.py:35` — `KLine.date` 是字符串，无采集时间戳
2. ❌ `src/data/models.py:19` — `StockQuote` 无 `collected_at`
3. ❌ `src/data/collector.py:160` — `meta.cached` 始终为 false

**修复方向**：
1. 在 KLine 和 StockQuote 模型中添加 `collected_at: datetime` 字段
2. DataCollector 填充缓存时自动记录采集时间
3. 前端数据卡片展示"数据时间: HH:mm:ss"
