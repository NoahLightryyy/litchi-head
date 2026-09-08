---
department: AI Agent 架构部
codebase: src/agents/ + src/core/
last_updated: 2026-08-26 (生产封口协调会：SAFE-1/PRICE-1 下发)
---

# 🤖 AI Agent 架构部工作交接

> 跨部门优先级与上下游交付以[后端主管总工作表](../00-cross-cutting/BACKEND-SUPERVISOR-WORKLIST.md)为准。

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
- **盘中证据分层**：Agent 同时接收历史 `FINAL_DAILY`、实时 `LIVE_QUOTE`、
  已结束 `FINAL_MINUTE` 和今日 `PROVISIONAL`；不得把动态状态写成收盘定论

---

## 开放债务

| ID | 描述 | 优先级 | 预估 |
|:---|:-----|:------:|:----:|
| TD-003 | MessageRouter 纯内存存储，进程重启丢失 | 🟡 | 1h |
| TD-006 | EvidenceItem 无校验逻辑 | 🟢 | 30min |
| TD-050 | XiaoZhiAgent 无 LLM 错误路径测试 | 🟡 | 30min |

---

## 下一步优先级

### 现有债务

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 🟡 | TD-003 MessageRouter 持久化（`save_snapshot/load_snapshot`） | 无 |
| 2 🟡 | TD-050 XiaoZhiAgent 补 LLM 超时/异常/非法返回测试 | 无 |
| 3 🟢 | TD-006 EvidenceItem 添加 `validate_chain()` 方法 | 无 |
| 4 🔥 | KR-4 提示词与结构化输出约束：区分 RAW 成交事实、点时前复权技术结构、实时事实与动态估算 | KR-3B-2 失败契约已冻结；等待用户确认是否继续 KR-4。AI 不直接读取累计快照、条款事件或证据仓 |

### 盘中分析约束（2026-07-30 确认）

1. 开盘后立即分析，不等待当日日 K 收盘；
2. 趋势、正式均线和日线形态只引用 `FINAL_DAILY`；
3. 当前价格、已结束分钟和今日动态 OHLC 可参与判断，但引用
   `PROVISIONAL` 时必须使用“盘中、正在形成、尚未确认”等措辞；
4. 不得把盘中最高/最低/动态收盘价描述为最终日线数据；
5. 如果上游没有提供证据状态，Agent 不得自行猜测或补全。
6. 前复权/后复权价格不能写成当前可买卖价格；下单价位只引用 `LIVE_QUOTE/RAW`；
7. 每项日线结论保留 `adjustment_mode`、`as_of` 和因子版本，方便结果复盘；
8. 原始或复权证据冲突由编排器在 Agent 启动前阻断，Agent 不承担“选一个源相信”的职责。

### 设计哲学新任务（DP 系列）

> 基于 2026-06-22 设计哲学会议。完整背景见 [DESIGN_PHILOSOPHY.md](../../00-overview/DESIGN_PHILOSOPHY.md)。

| DP | 事项 | 预估 |
|:--:|:-----|:----:|
| **DP-005** 🥇 | **灵感官 Agent** — 新增 `agents/agents_wild.py`，高随机性反共识分析师角色 | ~1h |

### 用户经验反馈闭环（UI 系列，2026-06-23 新增）

> 完整方案见 [USER_FEEDBACK_LOOP.md](../../02-requirements/USER_FEEDBACK_LOOP.md)。
> AI Agent 架构部在闭环中负责：DP-006 镜子 Agent 实现。

| UI | 事项 | 依赖 | 预估 |
|:--:|:-----|:----|:----:|
| **UI-4a** 🥉 | **DP-006 镜子 Agent**（全功能版）— 继承 `BaseAgent`，输出 `BehaviorComparisonReport`。MVP 版本由辩论引擎部 `src/debate/mirror.py` 实现（纯统计），全功能版需用户行为数据积累后再升级 | 后端 API 部 + 前端部 用户行为数据就绪 | ~3h |

### DP-005 灵感官设计要点

| 属性 | 值 |
|:-----|:----|
| 文件 | `src/agents/agents_wild.py` |
| 基类 | 复用 BaseAgent / MasterAgent |
| temperature | 0.9+（高随机性，区别于其他 Agent 的 0.3）|
| 注册 | AGENT_REGISTRY 注册，不加入辩论投票权重 |
| Prompt | "说出一个主流观点认为疯狂、但你确实有理由相信的可能性" |
| 输出 | 独立展示在前端"反共识观点"区，不参与主决策流 |

---

## 2026-08-26 协调会任务下发

**主责指标**：SAFE-1 下游安全、PRICE-1 价格坐标。

| 任务要求 | 部门验收口径 |
|:---------|:-------------|
| 约束四层数据语义 | `PROVISIONAL` 只能表述为盘中形成中；正式日线结论只引用 `FINAL_DAILY` |
| 区分研究坐标与成交坐标 | 复权价只描述技术结构；当前价、入场/止损/止盈只引用 `LIVE_QUOTE/RAW` |
| 结构化输出保留证据上下文 | 输出含 `as_of`、调整口径、因子版本、信封 ID 和证据限制/阻断原因 |
| 不承担失败仲裁 | 缺失或冲突由编排器在 Agent 启动前阻断，Agent 不猜测、不补全、不选源 |

**依赖闸门**：KR-3B-2 已冻结，KR-4 尚待用户转段确认；当前可审计提示词并准备语义
违规测试，但不得提前改写输入契约。

## 决策 baseline / 影子验证责任（TD-074）

完整口径见 [跨部门唯一协议](../../02-requirements/DECISION_BASELINE_AND_SHADOW_VALIDATION.md)。
Agent 必须输出可冻结的版本身份和结构化预测；不能查看 baseline 的后验结果，也不能在
结果到期后重新解释旧预测。真实校准样本不足时，confidence 只能表述为模型内部确信度，
不得称为真实胜率。

## 关键文件索引

| 文件 | 行数 | 说明 |
|:-----|:----:|:------|
| `src/agents/base.py` | 140 | Agent 基类 + AgentResult 泛型 |
| `src/agents/master_agent.py` | 232 | MasterAgent 通用实现（Skill+KB+LLM） |
| `src/agents/xiao_zhi.py` | — | 教育问答 Agent |
| `src/core/protocol.py` | — | 通信协议（MessageRouter, AgentMessage） |
| `docs/06-departments/03-ai-agents/ROLE.md` | — | 👤 AI Agent 架构部角色定义 |
| `docs/06-departments/03-ai-agents/STANDARDS.md` | — | 📐 AI Agent 架构部技术规范 |

## 前端总清单分工（FW）

> 总状态见[前端总工作清单](../../03-modules/10-frontend/WORKLIST.md)。

| 协调项 | 本部门细分责任 | 验收证据 |
|:-------|:---------------|:---------|
| FW-012/021 | Agent 输出明确区分 FINAL/PROVISIONAL、事实/估算和 RAW/复权语义 | 提示词与结构化输出不产生“已收盘”“可成交”等错误断言 |
| FW-050 | 产出镜子/行为比较所需结构化解释，保持建议与用户行为分离 | 不根据后验结果改写原建议；数据不足时明确限制 |
| FW-060 | 暴露模型、Prompt、配置和置信限制供效果证据追踪 | 同一冻结输入可追溯，不以模型自信替代真实胜率 |


## FW-041 用户下发：产业投资研究全景重构（2026-09-08）

总状态及完整需求见[FW-041唯一总表](../../03-modules/10-frontend/WORKLIST.md#fw-041-产业投资研究全景重构2026-09-08-用户下发)。本部门任务已登记，未启动实现。

- 本部门责任：提出瓶颈、关键节点、利润传导与情景研究判断方案。
- 交付与验收：重要性/瓶颈/投资吸引力分离；每项结论有事实、反证、解除条件与验证指标；不以模型自信替代置信依据。
- 上游依赖：数据事实目录；输出契约待冻结。
- 交接纪律：研究方案先于接口，后端契约冻结提交先于前端；不得将历史行业分类图标为当前瓶颈研究完成。既有来源授权沿用，新增资金默认值/超范围来源另行审定。

FW-041补充：多维个股研究应分别覆盖盈利质量、估值、成长、财务风险、产业位置与行情，说明指标标准、时间和缺项；不得按涨幅冒充AI评级。当前前端仅先取消旧字母并添加行情分类分页。详见FW-041总表的多维个股研究补充。
