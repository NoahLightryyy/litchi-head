---
department: 风控管理部
codebase: src/risk/
last_updated: 2026-07-30 (K 线完整性风控职责确认)
---

# 🛡️ 风控管理部工作交接

## 当前状态

### 模块完成度

| 子系统 | 状态 | 说明 |
|:-------|:----:|:------|
| 三层风控辩论编排 | ✅ | RiskOrchestrator 辩论链路风控节点 |
| RiskProfile 风险画像 | ✅ | 最大回撤/仓位/置信度阈值配置 |
| RiskAssessment 风险评估 | ✅ | 多维度结构化风控输出（波动率/回撤/集中度） |

### 测试

| 测试集 | 测试数 |
|:-------|:------:|
| 风险模块测试 | 26 |
| 风控编排链路 | 已覆盖 |

### 关键架构决策

- **独立判断**：风控不修改辩论结果，只返回 RiskAssessment
- **配置驱动**：所有风控阈值从 RiskProfile 读取，无硬编码
- **安全门禁**：风控未通过时，交易执行部不得执行

---

## 开放债务

当前无本部门独立债务；仍承担跨部门 TD-069/KR-4 和 TD-074。26 个测试通过只能证明
现有链路行为，不代表组合级硬风控或真实效果验证完成。

## 下一步优先级

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 🥈 | **RC-004 RP-TUNE 风险参数自适应** — 回测结果到达时，根据 max_drawdown / win_rate / sharpe 自动调整 stop_loss 和 position_size 覆盖值。通过 `CallbackStorage.load_risk_override()` 在风控辩论阶段消费 | 记忆系统部 RC-001（核心引擎）|
| 2 🥈 | **UI-2b 用户经验反馈闭环·风控参与** — 用户操作偏差检测（连续逆 AI 操作 → 标记风险行为模式 → 风控辩论参考） | UI-1 用户行为数据积累 | ~1h |
| 2 🟢 | 增加更多 RiskProfile 场景测试（保守/激进/平衡） | 无 |
| 🔥 | **TD-069/KR-4 数据完整性硬门禁** — RAW/复权冲突或独立源不足直接 `passed=false` | KR-2A 与 KR-2B-1 已完成，但累计快照尚无官方事件核验；等待 KR-2B-2 和 KR-3 统一信封。风控只消费 assessment/snapshot 引用，不自行查库或自行换算因子 |

**RC-004 调优规则概要**：

| 条件 | 调整 |
|:-----|:------|
| 最大回撤 > 8% | stop_loss_pct → min(当前, 5%)，max_single_position → min(当前, 15%) |
| 最大回撤 > 5% 且夏普 < 0.5 | stop_loss_pct *= 0.8 |
| 胜率 < 40% | max_single_position *= 0.8 |
| 总交易 < 5 次 | 不做调整（样本不足）|
| 最大回撤 > 10% 或夏普 < 0 | max_single_position → min(当前, 10%) |

## 决策 baseline / 影子验证责任（TD-074）

完整口径见 [跨部门唯一协议](../../02-requirements/DECISION_BASELINE_AND_SHADOW_VALIDATION.md)。
风控部负责把证据完整性、仓位、相关暴露、最大回撤和停止条件做成确定性代码门禁。
影子期参数不得根据少量胜负自动漂移；RC-004 启用前必须满足预注册样本门槛并保留旧版本。

---

## 关键文件索引

| 文件 | 行数 | 说明 |
|:-----|:----:|:------|
| `src/risk/orchestrator.py` | 488 | 风控辩论编排 |
| `src/risk/profiles.py` | 180 | 风险画像配置 |
| `src/risk/models.py` | — | 风控数据模型（RiskAssessment 等） |
| `docs/06-departments/05-risk-management/ROLE.md` | — | 👤 风控管理部角色定义 |
| `docs/06-departments/05-risk-management/STANDARDS.md` | — | 📐 风控管理部技术规范 |
