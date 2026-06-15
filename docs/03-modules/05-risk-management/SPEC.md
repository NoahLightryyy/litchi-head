# 功能模块：风控管理

> 交易决策的风险评估、仓位管理、止损止盈、合规检查。R1 三层风控辩论已实现，作为辩论流程的守门员层。

## 模块定义

交易决策的风险评估、仓位管理、止损止盈、合规检查。

**职责边界**：
- ✅ 仓位大小计算（基于置信度/风险偏好）
- ✅ 止损/止盈规则
- ✅ 多维度风险评估（市场风险/个股风险/流动性风险）
- ✅ 合规性检查（监管规则、资金约束）
- ✅ 三层风控辩论（Aggressive / Conservative / Neutral 三方交叉验证）
- ✅ 交易纪律检查（买入/卖出/仓位/加减仓纪律）
- ❌ 不负责交易决策生成（那是辩论模块的事）
- ❌ 不负责实际下单（那是交易执行模块的事）

## 代码结构

| 文件 | 说明 |
|------|------|
| `src/risk/__init__.py` | 模块公开接口（RiskAssessment, RiskRoundResult, TradeRecommendation 等） |
| `src/risk/models.py` | Pydantic 数据契约（RiskAssessment, RiskRoundResult, TradeRecommendation） |
| `src/risk/orchestrator.py` | 风控编排器：risk_round（三层风控） + pm_round（PM 最终裁决）节点工厂 |
| `src/risk/profiles.py` | 风控官人格定义（激进/保守/中性）+ 交易纪律体系（买入/卖出/仓位/加减仓） |

## 架构（当前状态）

```
辩论聚合（vote_summary）→ 风控审核（risk_round）→ PM 最终裁决（pm_round）
                                                                       
辩论投票汇总 ──────────→ 三层风控审核 ──────────→ Portfolio Manager
                           │                          │
                    ┌──────┼──────────┐               ├─ action (buy/sell/hold)
                    ↓      ↓          ↓               ├─ position_size_pct
            Aggressive  Conservative  Neutral          ├─ stop_loss_pct
            (机会成本)   (尾部风险)   (合规性)          ├─ take_profit_pct
                    │      │          │               ├─ discipline_checks_passed
                    └──────┼──────────┘               └─ key_warnings
                           ↓
                    RiskRoundResult
                    ├─ risk_consensus_action
                    ├─ avg_risk_score
                    ├─ min/max_position_pct
                    └─ total_discipline_violations
```

风控逻辑不再散落在 `DebateResult` 中，而是通过独立的 `risk_round` + `pm_round` 节点，集成在辩论编排器的末尾。

## 数据契约（关键模型）

| 模型 | 文件 | 用途 |
|------|------|------|
| `RiskAssessment` | `src/risk/models.py` | 单个风控官的结构化风险评估（action, position_size, stop_loss, risk_score, key_risks, discipline_violations 等） |
| `RiskRoundResult` | `src/risk/models.py` | 三位风控官汇总结果（共识操作、平均风险评分、仓位范围、纪律违规数） |
| `TradeRecommendation` | `src/risk/models.py` | PM 最终交易建议（action, position_size, stop_loss, take_profit, reasoning, risk_level, confidence, discipline_checks_passed） |

## 当前实现状态

| 特性 | 状态 | 测试数 |
|:-----|:----:|:------:|
| R1 三层风控辩论（risk_round + pm_round） | ✅ 已实现 | 8 |
| 交易纪律体系（买入/卖出/仓位/加减仓） | ✅ 已实现 | — |
| 与 DebateOrchestrator 集成（enable_risk 开关） | ✅ 已实现 | — |
| `enable_risk=False` 向后兼容 | ✅ 已验证 | — |
| 生产级风控规则引擎（vnpy 参考） | ⬜ Phase 3 | — |

## 下一步

- 🥇 风控辩论与现有辩论模块的深度联动（风控结果回传到辩论上下文）
- 🥈 生产级风控规则引擎参考 vnpy（交易风控 + 账户风控 + 合规检查）
- 🥉 更多维度风险指标（VaR、波动率、集中度自动计算）

> **关联文档**：[RESEARCH.md](RESEARCH.md) — 调研背景
