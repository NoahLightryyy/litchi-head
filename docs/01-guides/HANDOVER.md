# 🔄 AI 会话交接文档

> **用途**：上下文窗口达到上限，需要切换对话时，新会话从本文档恢复工作状态。
>
> **人类速查**：看 [HANDOVER_TIP.md](HANDOVER_TIP.md)（一页纸，扫一眼就够）。
>
> **上下文耗尽自动交接**：当 AI 检测到上下文接近上限时（~20K tokens 剩余），
> 自动执行交接流程（更新日志+债务+看板+提交），不推进新工作。
> 详细流程见 CLAUDE.md「上下文耗尽自动交接」节。

---

## 📋 如何读本文档

**本文档是全局仪表盘**，各部门的专有信息已下沉到各自部门文件夹：

```
docs/06-departments/
├── 00-cross-cutting/HANDOVER.md   ← 跨部门状态总览（推荐先读这个）
├── 01-data/HANDOVER.md            ← 数据管道部工作交接
├── 02-debate-engine/HANDOVER.md   ← 辩论引擎部工作交接
├── 03-ai-agents/HANDOVER.md       ← AI Agent 架构部工作交接
├── ...                             ← 其他部门同理
└── README.md                      ← 完整部门索引 + 协作规程
```

**工作流文档**也已完成按阶段拆分：

```
docs/01-guides/
├── WORKFLOW.md                       ← 索引（50 行，决策树导航）
└── workflow/
    ├── STARTUP.md                    ← 🚀 新会话启动 + 部门角色加载
    ├── DEVELOPMENT.md                ← 🔨 日常开发 + 代码规范
    ├── CLOSING.md                    ← ✅ 会话收尾 + 债务管理
    └── EMERGENCIES.md                ← ⚠️ 审视清单 + 突发情况
```

**各部门的债务**在 `DEBT.md` 中：
```
docs/06-departments/01-data/DEBT.md
docs/06-departments/02-debate-engine/DEBT.md
...
```

> **新 AI 启动**：执行 `/resume-session` Skill → 自动加载身份卡 + 当前状态 + 工作日志。

---

## 1. 项目身份卡

| 字段 | 值 |
|------|-----|
| **项目名称** | litchi-head — 多智能体投资决策平台 |
| **当前阶段** | Phase 1 MVP + Phase R 实盘加固 |
| **技术栈** | Python 3.12+ / LangGraph / DeepSeek-Chat / Pydantic / akshare / FAISS |
| **代码位置** | `e:\litchi-head` |
| **远程仓库** | GitHub (`origin`)，Gitee (`gitee`) 作为备份 |
| **默认分支** | `main` |
| **CI** | GitHub Actions（Ruff + Pyright + Pytest on 3.12/3.13） |
| **最新功能批次** | KR-3A 四层冻结契约与幂等收盘晋升完成；下一原子 KR-3B 运行时组装 |
| **全量测试** | 1692 collected；1669 passed / 4 skipped / 19 deselected；4/4 闸门通过 ✅ |
| **设计哲学** | 🏛️ [DESIGN_PHILOSOPHY.md](../00-overview/DESIGN_PHILOSOPHY.md) — 虚拟小投行蓝图；[PRODUCT-POSITIONING.md](../99-archive/PRODUCT-POSITIONING.md) — 2026-07-23 产品定位定论 |
| **Pyright** | src/ 0 errors, backend/ 0 errors ✅ |
| **CI 状态** | ✅ Run #72 全绿（frontend + Python 3.12/3.13）；本地全量闸门 4/4 通过 |

---

## 🏢 各部门一览

| 部门 | 代码 | 状态 | 开放债务 | → 看这里 |
|:-----|:-----|:----:|:--------:|:---------|
| 🗄️ 数据管道部 | `src/data/` + `src/data/indicators/` | 🟡 | 5 | [HANDOVER](../06-departments/01-data/HANDOVER.md) |
| 🎯 辩论引擎部 | `src/debate/` | 🟡 | 3 | [HANDOVER](../06-departments/02-debate-engine/HANDOVER.md) |
| 🤖 AI Agent 架构部 | `src/agents/` + `src/core/` | ✅ | 3 | [HANDOVER](../06-departments/03-ai-agents/HANDOVER.md) |
| 🧠 记忆系统部 | `src/memory/` | 🟡 | 2 | [HANDOVER](../06-departments/04-memory-systems/HANDOVER.md) |
| 🛡️ 风控管理部 | `src/risk/` | ✅ | 0 | [HANDOVER](../06-departments/05-risk-management/HANDOVER.md) |
| 💹 交易执行部 | `src/trader/` | ✅ | 0 | [HANDOVER](../06-departments/06-trading/HANDOVER.md) |
| 🔬 回测研究部 | `src/backtest/` | ✅ | 0 | [HANDOVER](../06-departments/07-backtesting/HANDOVER.md) |
| 🌐 后端 API 部 | `backend/` | 🟡 | 3 | [HANDOVER](../06-departments/08-backend-api/HANDOVER.md) |
| 🎨 前端部 | `frontend/` | ✅ | 1 | [HANDOVER](../06-departments/09-frontend/HANDOVER.md) |
| ⚙️ 基础设施部 | `src/utils/` | 🟡 | 7 | [HANDOVER](../06-departments/10-infrastructure/HANDOVER.md) |
| 🔄 质量保障部 | `.github/workflows/` + CI 文档 | 🟢 | 2 | [HANDOVER](../06-departments/11-quality-assurance/HANDOVER.md) |

**全代码库开放债务**: 34 条（紧急指数待重算）→ [债务路由](debt/ROUTER.md)

---

## 🎯 当前跨部门优先级

> **2026-07-31 战略校正**：当前主要矛盾是“系统建设能力强，真实结果验证能力弱”。
> 当前原子任务是 KR-3B 四层运行时组装；KR-3A 已完成。KR-3～KR-6 完成后，必须按
> [决策 Baseline 与影子验证计划](../02-requirements/DECISION_BASELINE_AND_SHADOW_VALIDATION.md)
> 进入 4～8 周影子验证。功能完成度、置信度字段和复盘页面不得表述为真实投资效果已验证。

> **2026-06-23 重排** — 基于 8 月底出国截止日期倒推。简历提交 9 月初。
> **核心约束**：先专注 A 股主体。美股列为 DLC（扩充包），A 股主体完工后再考虑。
> **完整时间线**：见 [ROADMAP.md](../00-overview/ROADMAP.md)「按 8 月底倒排的优先级」节。

### P0 — 实盘命脉（8 月中旬前完成）

| 优先级 | 事项 | 牵头部门 | 预估 |
|:------:|:-----|:---------|:----:|
| 🔥 **P0** | **PD-001/002/003 动态指标体系** — ✅ 全完成（34 tests + 325 ✅）详见跨部门总览 PD 节 |
| 🔥 P0 | **PD-004 行业覆盖验证 + 前端行业感知** — ✅ PD-004b 完成（FinancialPanel 按行业过滤指标）详见跨部门总览 PD 节 |
| 🔥 P0 | **ADR-012 数据生命周期与持久化底座** — 新闻 3 天滚动持久化与正式失败关闭完成；待扩展行情/K 线/行业 |
| 🔥 P0 | **C2 情绪数据层** — ✅ 已接入真实市场情绪数据（涨跌比+情绪评分），见 [2026-07-24-5 日志](../04-changelog/logs/2026-07-24/2026-07-24-5.md) |
| 🔥 P0 | **R4 置信度量化机制** — ✅ 校准曲线映射 + aggregate_node + 前端可视化已完成；真实概率校准仍依赖 TD-074 连续结果样本，见 [R4](../04-changelog/logs/2026-07-24/2026-07-24-5.md) |
| 🔥 P0 | **FD-001 基本面数据接入** — ✅ 全部完成：模型+Provider+多源财务数据+辩论注入+分析师增强+API 端点+前端财务 Tab | 全部门 ✅ | ~0 剩余 |
| 🔥 P0 | **交易复盘看板（极简版）** — ⟳ 后端完成（27 tests ✅）+ 前端组件完成 + 辩论自动记录已接入 | 后端 API 部+前端部 | ~2 天 |

### P1 — 提升赚钱概率（8 月底前）

| 优先级 | 事项 | 牵头部门 | 预估 |
|:------:|:-----|:---------|:----:|
| 🔥 P1 | **DP-004 TrustTracker 旋钮扩展** — ✅ 已完成：发言顺序排序 + 低信任跳过（min_trust_factor=0.7），见 [DP-004](../04-changelog/logs/2026-07-24/2026-07-24-5.md) | 辩论引擎部 | ~2h ✅ |
| 🔥 P1 | **DP-005 灵感官 Agent** — ✅ 已完成：第 5 位反共识分析师上线，见 [DP-005](../04-changelog/logs/2026-07-24/2026-07-24-5.md) | AI Agent 架构部 | ~1h ✅ |
| 🔥 P1 | **DP-007 信息隔离** — ✅ 已完成：analyst_round 后裁剪 market_data 原始数据数组，仅留 brief 文本 | 辩论引擎部 | ~2h ✅ |
| 🟡 P1 | **TD-041 数据新鲜度标注** — ✅ 已完成：KLine/StockQuote 添加 `fetched_at` 采集时间戳 + 前端数据新鲜度标签 + 缓存标记修复 | 数据管道部+前端部 | ~2h ✅ |

### P2 — 出国后迭代

| 事项 | 原预估 | 原因 |
|:-----|:------:|:-----|
| DP-006 镜子反思 | ~3h | ✅ 已完成（mirror.py + 19 tests） |
| UI Phase 2~4 完整闭环 | ~14h | 到国外安顿后迭代 |
| FD-003/004 供应链图谱 | ~5-7 天 | 有更好，没有也能炒 |
| Phase 3 实盘下单 | — | 先熟悉当地券商合规 |
| orchestrator.py 拆分 | — | 重构，不影响功能 |

### 🎮 DLC — 美股扩充包（A 股主体完工后再开）

| 事项 | 牵头部门 | 预估 | 原优先级 |
|:-----|:---------|:----:|:--------:|
| **YahooFinanceSource Provider** — 美股数据源（K 线+基本面+Provider Protocol） | 数据管道部 | ~半天 | 原 P0 |
| **美股前端 Tab** — 市场切换 + 美股行情 | 前端部 | ~半天 | 原 P0 |
| **美股新闻/财报事件接入** — 重大事件提醒 | 数据管道部 | ~1 天 | 原 P1 |

> 💡 **DLC 原则**：不推截止日期，A 股 AII（All In）完成后自然开启。

各部门的详细下一步 → 看各自 `HANDOVER.md` 的"下一步优先级"节。

---

## ▶️ 下次会话启动点（2026-07-30）

1. 新浪新闻元数据已进入 SQLite WAL 滚动缓存，默认每 5 分钟采集、保留 3 天；
2. 东方财富实时源与新浪滚动源通过同一接口并发聚合；
3. 正式辩论固定最近 3 天，任一新闻上游不完整即 HTTP 503；
4. 实时行情已迁移到东方财富 + 新浪双源门禁：10 秒新鲜度、3 秒配对、0.01 元
   容差；午休/收盘只展示，缺源或冲突即 HTTP 503；
5. 门禁测试确认分析师与大师 LLM 调用数均为零；
6. L1 分时战况已接入东方财富 + 腾讯分钟对账；分钟成交量统一为股，当前动态条
   标为 `PROVISIONAL`，不做主力/量化身份归因；
7. 用户已确认盘中 AI 不等待日 K 收盘：上一交易日及以前的完整日 K、实时行情、
   已结束分钟和今日 `PROVISIONAL` 动态状态必须同时进入上下文，但状态严格分离；
8. 用户已批准 K 线双源、复权和冲突口径，唯一决策源为
   [ADR-013](../05-decisions/ADR-013-multi-source-evidence.md)，实施顺序见
   [K 线证据完整性实施计划](../02-requirements/KLINE_EVIDENCE_IMPLEMENTATION_PLAN.md)；
9. TD-069/KR-1A 已完成：沪深新浪+腾讯 RAW 独立上游、`RawDailyBar` 单位/精度、
   OHLC 严格对账、当日动态排除和北交所 `INCOMPLETE`；25 项契约、85% 专项覆盖
   与沪深北真实烟测通过，旧 K 线入口未切换；
10. 实时行情 `0.01 元` 容差、分钟累计量 `500 股` 经验容差和完成日线 RAW 严格
    对账是三套不同规则，禁止跨场景复用；
11. 下一原子功能是 KR-1B：用经过批准的交易日历与个股停牌状态生成预期完成交易
    日集，并补 RAW/逐源诊断持久化和长窗覆盖证明；新增数据源属于方向性决策，必须
    先让用户确认，不能用工作日猜测停牌；
12. 用户已确认免费官方方案；KR-1B-1 已完成三市场 2026 官方日历版本和预期日期
    集门禁。两源共同漏开市日返回 `expected_trading_date_missing`，越出日历覆盖
    返回 `calendar_coverage_missing`；真实 `300996` 停牌样本已按此失败关闭；
13. KR-1B-2A 官方证券状态契约已完成：覆盖窗口、上市/退市边界、全天停牌、
    盘中临停、官方链接和内容哈希已类型化；不得重复定义第二套状态模型；
14. KR-1B-2B 已把状态窗口串联日线运行时：官方覆盖完整时过滤全天停牌/生命周期
    日期，覆盖不足返回 `security_status_coverage_missing`；
15. KR-1B-2C-1 已完成 CNINFO 上市公司法定披露 PDF 的停复牌事件采集：只接受
    正文明示的生效日，保留附件 URL/SHA-256；真实 `300996` 的 7 月 27/29 日停牌
    和 30 日复牌已通过。事件层不等于完整状态窗口，生产运行时仍未装载在线目录；
16. KR-1B-2C-2A 连续状态账本已完成：官方生命周期 + 状态检查点 + 连续查询批次
    才能生成窗口；重复公告幂等归并，断档/冲突/锚点不足失败关闭，并保留已公告但
    尚未生效的转换。不得重复实现第二套状态归并器；
17. KR-1B-2C-2B 已完成：`providers/lifecycle.py` 直连沪深官方上市/退市清单，
    CNINFO 查询生成完整自然日覆盖批次与响应哈希，账本可生成确定性检查点并保留
    未来转换；沪深在市/退市样本和 `300996` 跨批次链路已烟测；
18. KR-1B-2C-2C 已完成：北交所上市清单/代码映射/市场日历独立适配，严格校验
    分页、分类计数和身份；`0600/0700` 进入既有账本，`9001` 不冒充全天停牌。
    三家历史转板股因缺结构化上市日明确失败，见 TD-073；
19. KR-1B-3A/3B 已完成：`KlineAuditStore` 保存不可变逐源 RAW/诊断/权威引用，
    腾讯长窗按不超过 1000 日连续分段并记录准确响应证明；新浪只有最早原始日期
    覆盖请求起点才算完整，否则保留部分 RAW 并
    `STALE / kline_source_window_not_covered`；
20. 正式 `collect_and_persist()` 已接入上述证明和存储，但仍是数据部旁路，尚未
    切入 AI/API。完整快照必须有日历权威且 canonical 的日期/值可追溯到成功源
    RAW；缺权威日历、状态覆盖、来源覆盖或任一异常均失败关闭；
21. KR-2A 已完成：`src/data/kline_adjustment.py` 提供冻结的版本化公司行动因子、
    精确股本比例/来源精度核验、内容哈希、KR-1 快照完成证明绑定和点时 QFQ；
    26 项契约通过；该条只记录 2A 阶段边界，整个 KR-2 已于 2026-08-04 完成；
22. 用户已确认 KR-2B 方案 A：沪深使用新浪直连累计 QFQ 除数，CNINFO/交易所
    正式披露承担独立事件核验；Tushare、BaoStock、AKShare 包装层不接入，北交所
    在自己的官方事件核验完成前失败关闭；
23. KR-2B-1 已完成：`src/data/providers/sina_adjustment.py` 保存原始响应哈希、
    Decimal 精度和累计除数快照，区分网络失败/脏响应/BSE 不支持；沪深真实冒烟
    通过。该快照不是 `CorporateActionFactor`，不得直接进入复权或 AI；
24. KR-2B-2A 已完成：`OfficialCorporateActionDocument/Event` 冻结公告原文
    哈希、修订、登记/除权日、解析器版本、严格金额/比例和六类事件条款矩阵；
    38 项契约通过。
    这只是领域契约，没有联网解析或已核验因子；
25. KR-2B-2B1 已完成：`CninfoCorporateActionSource` 解析深市标准权益分派实施
    公告并按除权日聚合；真实 `000001` 样本得到每股 `0.36200`；
26. 2B2A/2B2B 已完成：SSE 普通/差异化模板、配股最终发行日程、实际派发/除权
    调整双现金口径，以及更正/延期/终止公告联网归链。缺原公告时同源回填 365 天；
    引用缺失、歧义、倒序或缺更正后完整正文均失败关闭；
27. KR-2B-2C 转换核心已完成：相邻累计除数与官方现金/股本/配股条款、登记日 RAW
    公式复算；16 位尾差按用户批准的 12 位 `ROUND_HALF_EVEN` 门限验证并降级输出
    精度。`000001` 三次真实事件通过；
28. TD-072 代码已完成：腾讯五日历史只进入影子分区，双源完整日进入正式分区；
    内容寻址 Parquet + SQLite 清单支持篡改失败关闭，API 明示影子限制。继续积累
    20个双源日并做误报率验证，不阻塞 K 线门禁；
29. TD-075 已关闭：SSE 相同重复日期表幂等、不同日期冲突；“修订版”完整正文和
    PDF 标题空白归一进入唯一修订链；`600000/688008/688503` 及三上游故障烟测
    通过。KR-2 完成，下一步按 KR-3～KR-6 推进四层信封、AI/风控/交易、API/前端
    和全链路验收。
30. KR-3A 已完成：`src/data/kline_business.py` 冻结四层成功信封和四层诊断失败
    结果；完成分钟与 RAW 实时行情深度不可变，动态日线无法混入 `FINAL_DAILY`；
    收盘晋升按内容生成确定性 ID，相同重试幂等、冲突证据拒绝覆盖。下一原子只做
    KR-3B 现有日线/分时/实时运行时组装，不提前进入 AI/API。

---

## 关键设计决策（跨部门）

### 技术红线

1. **所有 LLM 调用必经 `src/utils/llm.py`** — 不得直接实例化 `ChatDeepSeek` / `ChatOpenAI`
2. **Pydantic 作为模块间数据契约** — `@dataclass` 仅限模块内部，跨模块传递用 `BaseModel`
3. **类型注解必须完整** — Pyright basic mode 零错误
4. **五同步原则** — 代码 + 测试 + 文档 + 债务日志 + **引用清理**同步更新
5. **Agent 输出结构化** — 含评分/证据/置信度，非纯文本
6. **LLMService 调用走 `LLMConfig`** — 不硬编码 temperature/max_tokens

### AgentResult 泛型化

```python
# 向后兼容（已有代码不变）
result = AgentResult(data={"key": "val"})

# 新写法（类型化输出，Pyright 可静态校验）
result = AgentResult[NewsOutput](data=NewsOutput(...))
result.data.summary  # Pyright 可校验 ✅
```

---

## 工作流优化建议

### 已知效率问题

| 问题 | 修复方案 | 状态 |
|:----|:---------|:----:|
| 质量修复循环过多 | PostWrite hook 自动 `ruff check --fix` | ✅ 已配置 |
| pandas 类型反复 | 必须 `str(row["col"])` 显式转换 | ✅ 已记录 |
| CI 红着没人修 | Batch Loop 收尾前自动跑 `ruff check .` + `pyright src/` | ✅ |
| Windows torch crash | `__init__.py` 惰性导入 | ✅ 已解 |
| 手动 make check 跑全量测试太慢 + Windows 无 make | `scripts/check.py` 跨平台替代 + 智能按变更选测试（~40s 日常，~3min 全量子集） | ✅ 2026-06-23 |

### pandas 类型模式（必须遵守）

```python
# ❌ 错误
StockInfo(code=row["code"], name=row["name"])

# ✅ 正确
StockInfo(code=str(row["code"]), name=str(row["name"]))
StockQuote(price=float(row["最新价"]), volume=int(row["成交量"]))
```

---

## 7. 常见问答

**Q：AgentResult 改成 BaseModel 后，现有测试需要改吗？**
A：不需要。`data: dict | T = Field(default_factory=dict)` 确保向后兼容。

**Q：集成测试为什么跳过？**
A：代理环境屏蔽东方财富 API，`urllib.request.urlopen(..., timeout=3)` 检测失败时自动跳过。CI 环境正常跑。

**Q：我要进某个部门工作，先看什么？**
A：`docs/06-departments/{id}/ROLE.md` → 了解角色 → `STANDARDS.md` → 技术规范 → `HANDOVER.md` → 当前状态 → `DEBT.md` → 债务。

**Q：WORKFLOW.md 怎么变这么短了？**
A：从 1047 行拆成了 4 份聚焦文档。索引在 [WORKFLOW.md](WORKFLOW.md)，启动看 [workflow/STARTUP.md](workflow/STARTUP.md)，干活看 [workflow/DEVELOPMENT.md](workflow/DEVELOPMENT.md)，收尾看 [workflow/CLOSING.md](workflow/CLOSING.md)，出问题看 [workflow/EMERGENCIES.md](workflow/EMERGENCIES.md)。

---

> **最后更新**：2026-07-29 | 新闻 3 天滚动证据与正式辩论失败关闭完成
