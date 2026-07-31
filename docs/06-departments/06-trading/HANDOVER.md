---
department: 交易执行部
codebase: src/trader/
last_updated: 2026-07-30 (K 线口径与交易价格边界确认)
---

# 💹 交易执行部工作交接

## 当前状态

### 模块完成度

| 子系统 | 状态 | 说明 |
|:-------|:----:|:------|
| TradePlan/TradeRecord/TradeOrder 模型 | ✅ | Pydantic 结构化交易数据 |
| TraderOrchestrator 交易编排 | ✅ | 执行链路（含风控门禁 + 置信度门禁） |
| TraderProfile 交易画像 | ✅ | 交易策略偏好配置 |
| 辩论→交易桥接（bridge.py） | ✅ | TradePlan → TradeRecord 转换 |

### 测试

| 测试集 | 测试数 |
|:-------|:------:|
| 交易模块测试 | 20 |
| 桥接适配器测试 | 14 |
| **合计** | **34** |

### 关键架构决策

- **双重安全门禁**：执行前必须通过风控检查 + 置信度阈值检查
- **可追溯性**：每笔 TradeRecord 关联 debate_id，可回溯到辩论
- **严格职责分离**：交易部不质疑分析，不修改风控，只执行

---

## 开放债务

当前无本部门独立债务；仍承担跨部门 TD-069/KR-4 和 TD-074。34 个测试通过不代表
真实成交、成本或不可成交处理已完成验证。

## 下一步优先级

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 🟢 | 增加更多边界测试（空 TradePlan/极高仓位） | 无 |
| 🔥 | **TD-069/KR-4 价格坐标门禁** — 下单/止损/止盈只使用 `LIVE_QUOTE/RAW`；复权技术位必须换回 RAW | KR-2A 已分离价量口径，KR-2B-1 仅提供累计快照；等待 KR-2B-2/4 接入经官方事件核验的因子。交易只保存/核对 snapshot 引用，不把累计除数或复权价当成交价 |

## 决策 baseline / 影子验证责任（TD-074）

完整口径见 [跨部门唯一协议](../../02-requirements/DECISION_BASELINE_AND_SHADOW_VALIDATION.md)。
交易部负责统一 RAW 成交坐标、手续费、印花税、滑点、停牌和涨跌停等执行规则。AI 与
baseline 必须使用完全相同的成交假设；影子阶段不得自动下单。

---

## 关键文件索引

| 文件 | 行数 | 说明 |
|:-----|:----:|:------|
| `src/trader/orchestrator.py` | 427 | 交易执行编排 |
| `src/trader/bridge.py` | 260 | 辩论→交易桥接 |
| `src/trader/profiles.py` | — | 交易画像配置 |
| `src/trader/models.py` | — | 交易数据模型 |
| `docs/06-departments/06-trading/ROLE.md` | — | 👤 交易执行部角色定义 |
| `docs/06-departments/06-trading/STANDARDS.md` | — | 📐 交易执行部技术规范 |
