# DP-003 偏斜公示 — 设计文档

> **阶段**：Phase 1 MVP
> **状态**：已审批待实现
> **更新**：2026-06-23
> **牵头部门**：辩论引擎部 + 后端 API 部

---

## 背景

每次辩论的投票汇总（`VoteSummary`）已统计方向分布（`direction_distribution`），但未将分布整合为可消费的偏斜度指标。用户/前端无法直观判断"群体情绪是偏乐观还是偏悲观"以及"观点分歧有多大"。

## 目的

在 `VoteSummary` 中新增 `BiasReport` 字段，将分布数据计算为结构化偏斜报告，供前端展示和后续历史分析。

## 设计方案

### 1. BiasReport 模型

在 `src/debate/models.py` 中新增，挂在 `VoteSummary` 上：

```python
class BiasReport(BaseModel):
    """辩论产出偏斜度报告（在 D4 聚合阶段计算，不增加 LLM 调用）"""
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    total_count: int = 0

    bullish_ratio: float = 0.0
    bearish_ratio: float = 0.0
    neutral_ratio: float = 0.0

    # 总体偏斜度 (bullish - bearish) / total
    # +1 = 全体看涨，-1 = 全体看跌，0 = 均衡或全中性
    overall_bias: float = 0.0

    # 共识强度 max(bullish, bearish, neutral) / total
    # 0~1，高=观点集中，低=分歧大
    consensus_strength: float = 0.0

    # "Bullish" | "Bearish" | "Neutral" | "Divided"
    consensus_type: str = "Neutral"

    # 历史平均偏斜度（占位，持久化留后续实现）
    historical_avg_bias: float = 0.0
```

### 2. 挂载位置

`BiasReport` 作为 `VoteSummary` 的字段，随 `DebateResult` 一起返回：

```python
class VoteSummary(BaseModel):
    # ... 现有字段不变 ...
    bias_report: BiasReport = Field(default_factory=BiasReport)
```

### 3. 计算公式

在 `aggregate_node` 中 `direction_distribution` 构建完毕后追加计算：

```
bullish = direction_distribution.get("Bullish", 0)
bearish = direction_distribution.get("Bearish", 0)
neutral = direction_distribution.get("Neutral", 0)
total   = bullish + bearish + neutral (= total_votes)

overall_bias      = (bullish - bearish) / total       — 除零保护
consensus_strength = max(bullish, bearish, neutral) / total  — 除零保护
```

共识类型判定：

| 条件 | consensus_type |
|:-----|:---------------|
| total == 0 | "Neutral" |
| max_count / total > 0.5 且最大是 Bullish | "Bullish" |
| max_count / total > 0.5 且最大是 Bearish | "Bearish" |
| max_count / total > 0.5 且最大是 Neutral | "Neutral" |
| 无任一占比过半 | "Divided" |

### 4. `to_summary_dict()` 输出

在 `DebateResult.to_summary_dict()` 中追加偏斜字段（仅当有分析师时）：

```python
if vs.direction_distribution:
    result["偏斜报告"] = {
        "总体偏斜": vs.bias_report.overall_bias,
        "共识强度": vs.bias_report.consensus_strength,
        "共识类型": vs.bias_report.consensus_type,
        "看涨": vs.bias_report.bullish_count,
        "看跌": vs.bias_report.bearish_count,
        "观望": vs.bias_report.neutral_count,
    }
```

### 5. 范围界限

| 做 | 不做 |
|:---|:-----|
| BiasReport 模型定义 | 前端完整 UI 实现 |
| `aggregate_node` 中偏斜计算 | 历史偏斜持久化（留坑位） |
| `to_summary_dict()` 输出 | orchestrator.py 拆分 |
| 15-20 个新增测试 | 任何新 LLM 调用 |
| 前端 TypeScript 类型更新 | 新 Agent 轮次 |
| 文档同步 | |

### 6. 测试策略

| 测试集 | 测试内容 | 数量 |
|:-------|:---------|:----:|
| `test_bias_report_model` | 模型构造、默认值、各种分布场景 | ~7 |
| `test_aggregate_node_bias` | 集成到 aggregate_node 的偏斜计算 | ~5 |
| `test_to_summary_dict_bias` | `to_summary_dict()` 输出偏斜字段 | ~3 |
| `test_edge_cases` | 空分布 / 平局 / 仅一个分析师 | ~3 |
| **合计** | | **~18** |

### 7. 文件改动清单

| 文件 | 改动 |
|:-----|:------|
| `src/debate/models.py` | +BiasReport 模型，VoteSummary 加 bias_report 字段 |
| `src/debate/orchestrator.py` | aggregate_node 中 +偏斜计算逻辑 |
| `frontend/lib/types/debate.ts` | +BiasReport TypeScript 类型 |
| `tests/test_debate/` | +test_bias_report.py 新测试文件 |

## 场景验证

| 分布 | overall_bias | consensus_strength | consensus_type | 解读 |
|:----|:-----------:|:-----------------:|:-------------|:-----|
| 5:0:1 | +0.83 | 0.83 | Bullish | 群体强烈看涨 |
| 3:2:1 | +0.17 | 0.50 | Divided | 偏涨但分歧大 |
| 0:0:6 | 0.0 | 1.0 | Neutral | 全体选择谨慎观望 |
| 1:4:1 | -0.50 | 0.67 | Bearish | 群体偏悲观 |
| 2:2:2 | 0.0 | 0.33 | Divided | 观点完全分裂 |
| 1:1:1 | 0.0 | 0.33 | Divided | 三足鼎立，无共识 |

---

> **关联阅读**：[辩论引擎部 ROLE.md](../ROLE.md) | [VoteSummary 模型](../../../../src/debate/models.py)
