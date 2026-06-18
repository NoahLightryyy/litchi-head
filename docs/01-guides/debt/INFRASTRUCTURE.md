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

---

###### TD-056 CI 流水线无覆盖率门禁

| 属性 | 值 |
|------|-----|
| **分类** | `⚙️ infrastructure` `severity:critical` `module:ci` `impact:质量防线` |
| **发现日期** | 2026-06-18 |
| **发现人** | AI 按察审计 |
| **修复日期** | 2026-06-18 |
| **状态** | `✅ 已修复` |
| **实际工时** | ∼10min |
| **实盘影响** | 🔴 项目宣称"80% 覆盖率目标"但 CI 从未验证过。2026-06-18 首次实测为 88%，但无法阻止未来降级 |
| **触发场景** | 每次 PR 合并 — 新代码可能降低覆盖率且无人知道 |
| **用户能发现吗** | ❌ 不能 — 覆盖率是内部指标，但下降意味着质量失守 |

**描述**：
`.github/workflows/ci.yml` 中无任何覆盖率检查步骤。`pyproject.toml` 虽有 `[tool.coverage.run]` 配置但从未启用。无法阻止「新代码没测试→覆盖率下降→质量失守」的滑坡。

**具体数据**（2026-06-18 首次实测）：
- 全量：88%（3424 行，413 未覆盖）
- Provider 层：30-55%
- backend/：0% 🔥

**修复方向**：
1. 在 CI 中添加 `coverage run -m pytest && coverage report --fail-under=80`
2. 设置覆盖率 PR 门禁（GitHub Actions 中 fail < 80%）
3. 债务看板自动生成脚本，每次 CI 更新 ROUTER.md 中的实时指标

---

###### TD-058 安全审计从未执行

| 属性 | 值 |
|------|-----|
| **分类** | `⚙️ infrastructure` `severity:critical` `module:all` `impact:安全` |
| **发现日期** | 2026-06-18 |
| **发现人** | AI 按察审计 |
| **修复日期** | 2026-06-18 |
| **状态** | `🔧 修复中` |
| **本金估算** | ∼1h |
| **实际工时** | ∼30min（首次扫描 + 关键依赖升级） |
| **实盘影响** | 🔴 项目运行至今从未进行过任何安全扫描。API 密钥明文存储在 `.env` 中，依赖可能有已知 CVE 无人知道 |
| **触发场景** | 密钥泄露、依赖漏洞被利用 |
| **用户能发现吗** | ❌ 不能 — 直到收到天价 API 账单或系统被入侵 |

**描述**：
以下安全工具均为零配置、零运行：
1. ❌ `bandit` — Python 代码安全扫描从未安装/运行
2. ❌ `pip-audit` — 依赖漏洞扫描从未执行
3. ❌ `safety` — Python 依赖已知漏洞检查从未运行
4. ❌ CI 中无任何安全扫描步骤
5. ❌ `.env` 包含真实的 DEEPSEEK_API_KEY 和 ANTHROPIC_API_KEY 明文（关联 TD-038）

**修复方向**：
1. ✅ 安装 bandit + pip-audit
2. ✅ 首次全量扫描
3. ✅ 升级关键依赖：langchain 1.3.4→1.3.9 / requests 2.32.5→2.34.2 / tornado 6.5.5→6.5.7
4. ⬜ 加入 CI 流水线（作为单独步骤，不阻塞构建）
5. ⬜ 轮换当前所有明文存储的 API 密钥

**首次扫描结果（2026-06-18）**：

| 扫描工具 | 结果 |
|:---------|:-----|
| bandit (src/ + backend/) | 8 个 Low 级别 assert_used，0 个 HIGH/MEDIUM ✅ |
| pip-audit | 17 个已知 CVE（修复 6 个运行时关键依赖后剩余 11 个） |

**剩余 11 个未修复 CVE 说明**：
| 包 | 原因 |
|:---|:-----|
| bleach 6.3.0 | HTML 净化工具，非运行时核心，修复需升级到 6.4.0 |
| idna 3.11 | URL 编码库，transitive 依赖 |
| pip 26.0.1 | 包管理工具，非运行时 |
| urllib3 2.6.3 | HTTP 库，requests 的 transitive 依赖 |
| torch 2.12.0 | 无可修复版本 |

---

###### TD-061 依赖漏洞扫描从未执行

| 属性 | 值 |
|------|-----|
| **分类** | `⚙️ infrastructure` `severity:moderate` `module:all` `impact:安全` |
| **发现日期** | 2026-06-18 |
| **发现人** | AI 按察审计 |
| **修复日期** | 2026-06-18 |
| **状态** | `✅ 已修复` |
| **本金估算** | ∼30min |
| **实际工时** | ∼15min |
| **实盘影响** | 🟡 项目使用 50+ 第三方依赖，可能存在已知 CVE 未被检测。例如 akshare、pydantic、fastapi 等核心依赖若有安全更新，当前流程不会通知 |
| **触发场景** | 依赖出现严重 CVE（如 log4j 式事件） |
| **用户能发现吗** | ❌ 不能 — 漏洞是供应链问题，无外部表现直至被利用 |

**描述**：
从未运行过 `pip-audit` 或 `safety check`。依赖安全完全是盲区。

**修复方向**：
1. `pip install pip-audit && pip-audit` 首次扫描
2. 加入 CI 流水线（`pip-audit` 作为独立步骤，仅 warn 不 block）
