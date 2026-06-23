---
department: 辩论引擎部
codebase: src/debate/
last_updated: 2026-06-23
---

# 🎯 辩论引擎部工作交接

## 当前状态

### 模块完成度

| 子系统 | 状态 | 说明 |
|:-------|:----:|:------|
| 9 层辩论链路（data→analyst→review→vote→risk→trader→pm→reflection→summary） | ✅ | LangGraph StateGraph 编排 |
| D1 交叉审阅（赞同+补充+异议三段式） | ✅ | 大师间双向三段式互评 |
| D2 强制输出方向 | ✅ | 按市场环境约束辩论方向 |
| D3 独立评审 | ✅ | 第三方独立评判 |
| D4 加权投票汇总 | ✅ | 含 M3 信任度因子叠加 |
| M1 历史决策注入 | ✅ | 前次辩论决策参考 |
| M2 反思闭环（reflection.py） | ✅ | Record→Compare→Reflect→Inject |
| M3 信任度评分（trust.py） | ✅ | 759 行信任度追踪系统 |
| M4 动态权重 | ✅ | 信任度→投票权重映射 |
| R1 三层风控辩论（risk/） | ✅ | src/risk/ 独立模块 |

### 测试

| 测试集 | 测试数 |
|:-------|:------:|
| 辩论编排器（test_orchestrator） | 17 |
| D1 交叉审阅（test_d1_cross_review） | 25（✅ DP-002 三段式改造） |
| D2 方向约束（test_d2_direction） | 31 |
| D3 独立评审（test_d3_independent） | 23 |
| M1 历史注入（test_m1_history） | 22 |
| D4 投票扩展（test_d4_vote） | 15 |
| 信任度（test_trust） | 54 |
| M4 动态权重（test_m4_dynamic） | 10 |
| **辩论模块合计** | **235** |

### 关键指标

- LLM 调用/辩论：~12-15 次（目标 ≤ 8 次）
- 全链路耗时含 LLM：~20-30s
- 置信度量化：全部输出带评分 + 置信度

---

## 开放债务

| ID | 描述 | 优先级 | 预估 |
|:---|:-----|:------:|:----:|
| TD-018 | 编排层成本优化 — 9 层链路无短路，~15 次 LLM 调用 | 🟡 | 1d |
| TD-017 | 缺少反思/学习闭环（M2 交易后反思） | 🟢 | 2d |

### 文件大小超标

| 文件 | 行数 | 红线 | 行动 |
|:-----|:----:|:----:|:-----|
| `orchestrator.py` | **1622** | 800 | 🔴 需拆分（计划见 STANDARDS.md） |
| `trust.py` | **759** | 800 | 🟡 接近红线 |

---

## 下一步优先级

### 现有债务

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 🔴 | **拆分 orchestrator.py**（1622→800）— 按节点拆分到 `orchestrator/nodes/` 目录 | 无 |
| 2 🟡 | TD-018 成本优化 — 短路优化、层合并、模型分层 | 无 |

### 设计哲学新任务（DP 系列）

> 基于 2026-06-22 设计哲学会议。完整背景见 [DESIGN_PHILOSOPHY.md](../../00-overview/DESIGN_PHILOSOPHY.md)。

| DP | 事项 | 预估 |
|:--:|:-----|:----:|
| **DP-002** 🥇 | **D1 同侪审阅** — prompt 从"反驳"改为"赞同+补充+异议"三段式审阅，测试验证输出结构变化但无回归 | ✅ 已完成 |
| **DP-003** 🥇 | **偏斜公示** — D4 聚合后统计正面/负面观点比例，输出偏斜度（`BiasReport`）供前端消费 | ~1h |
| **DP-004** 🥇 | **TrustTracker 旋钮扩展** — 增加 `发言顺序权重`、`参与资格阈值`、`置信度校准系数` 三种新旋钮，全用公式计算不经过 LLM | ~2h |
| **DP-006** 🥈 | **镜子反思** — 辩论结束后产出一份历史对比（上次类似市况谁的判断准），展示给用户看，不自动注入 | ~2h |
| **DP-007** 🥈 | **信息隔离** — StateGraph 每层结束后裁剪 state，只保留该层的 Pydantic 结构化 model，删除原始 prompt 和中间结果 | ~2h |

### DP-003 偏斜度输出接口

```python
# D4 聚合后新增
@dataclass
class BiasReport:
    positive_count: int          # 正面观点数
    negative_count: int          # 负面观点数
    buy_ratio: float             # 买入建议比例
    sell_ratio: float            # 卖出建议比例
    hold_ratio: float            # 持有建议比例
    overall_bias: float          # 总体偏斜度（正=偏乐观，负=偏悲观）
    historical_avg_bias: float   # 历史平均偏斜度
```

### 关联文件

| 文件 | 说明 |
|:-----|:------|
| `src/debate/trust.py` | 759 行 → 扩展旋钮（DP-004） |
| `src/debate/orchestrator.py` | 1622 行 → DP-002 修改 review prompt 为三段式 |
| `src/debate/models.py` | 368 行 → 加 `BiasReport`、`MirrorReport` |
| `src/debate/orchestrator.py` | 1622 行 → state 裁剪（DP-007）

---

## 关键文件索引

| 文件 | 行数 | 说明 |
|:-----|:----:|:------|
| `src/debate/orchestrator.py` | 1622 | 🔴 编排器主体（需拆分） |
| `src/debate/trust.py` | 759 | 🟡 信任度评分引擎 |
| `src/debate/models.py` | 368 | 辩论数据模型（D1-D4 + M1-M4） |
| `src/debate/reflection.py` | 345 | M2 反思闭环 |
| `src/debate/analysts.py` | 135 | 大师分析师 Prompt |
| `src/risk/orchestrator.py` | 488 | 风控辩论编排 |
| `src/risk/profiles.py` | 180 | 风险画像配置 |
| `docs/06-departments/02-debate-engine/ROLE.md` | — | 👤 辩论引擎部角色定义 |
| `docs/06-departments/02-debate-engine/STANDARDS.md` | — | 📐 辩论引擎部技术规范 |
