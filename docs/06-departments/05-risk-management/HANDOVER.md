---
department: 风控管理部
codebase: src/risk/
last_updated: 2026-06-21
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

当前无开放债务（26 测试通过，风控链路正常）

## 下一步优先级

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 🟢 | 增加更多 RiskProfile 场景测试（保守/激进/平衡） | 无 |

---

## 关键文件索引

| 文件 | 行数 | 说明 |
|:-----|:----:|:------|
| `src/risk/orchestrator.py` | 488 | 风控辩论编排 |
| `src/risk/profiles.py` | 180 | 风险画像配置 |
| `src/risk/models.py` | — | 风控数据模型（RiskAssessment 等） |
| `docs/06-departments/05-risk-management/ROLE.md` | — | 👤 风控管理部角色定义 |
| `docs/06-departments/05-risk-management/STANDARDS.md` | — | 📐 风控管理部技术规范 |
