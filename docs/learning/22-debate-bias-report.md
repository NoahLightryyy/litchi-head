# ⚖️ 辩论偏斜度计算（BiasReport）

## 一句话

> 通过统计学指标量化辩论群体的情绪倾向和观点集中程度。
> 一句话：把"谁说了什么"变成"群体到底怎么看"。

---

## 为什么需要它？

### 问题场景

一场辩论结束后，你有 7 位大师的分析结果：有人看涨、有人看跌、有人观望。你是用户，你想快速知道——**这群人整体是乐观还是悲观？他们意见一致还是分裂？**

只看原始数据（`direction_distribution: {"Bullish": 4, "Bearish": 1, "Neutral": 2}`），你得自己心算比例，而且"偏斜度 0"可能有两种截然不同的含义：全体观望 vs 深度分歧。

### 它的解法

**三个指标解开所有信息：**

| 指标 | 公式 | 含义 |
|:-----|:-----|:------|
| **总体偏斜度** | (Bullish - Bearish) / Total | 群体方向偏好，-1~+1 |
| **共识强度** | max(Bullish, Bearish, Neutral) / Total | 观点集中度，0~1 |
| **共识类型** | 见下文 | 群体状态分类 |

关键是**共识类型区分了两种偏斜度为 0 的场景**：
- `Neutral` = 全体谨慎（有意识的不出手）
- `Divided` = 观点分裂，无明确多数

---

## 项目里的真实代码

打开 `src/debate/orchestrator.py` 找到 `compute_bias_report` 函数：

```python
def compute_bias_report(direction_distribution: dict[str, int]) -> BiasReport:
    bullish = direction_distribution.get("Bullish", 0)
    bearish = direction_distribution.get("Bearish", 0)
    neutral = direction_distribution.get("Neutral", 0)
    total = bullish + bearish + neutral

    if total == 0:
        return BiasReport()

    overall_bias = round((bullish - bearish) / total, 4)
    consensus_strength = round(max(bullish, bearish, neutral) / total, 4)

    # 共识类型判定
    if max(bullish, bearish, neutral) / total > 0.5:
        if bullish > bearish and bullish > neutral:
            consensus_type = "Bullish"
        elif bearish > bullish and bearish > neutral:
            consensus_type = "Bearish"
        else:
            consensus_type = "Neutral"
    else:
        consensus_type = "Divided"

    return BiasReport(...)
```

**为什么用公式不用 LLM？** 偏斜度是纯粹的统计学指标——LLM 不需要参与。数学公式确定、可测试、无 token 成本。这也符合辩论引擎部的"最少 LLM 调用原则"。

---

## 共识类型判定逻辑

```
max(bullish, bearish, neutral) / total > 0.5 ?
  ├── 是 → 有明确多数 → 把最多的那个当成共识类型
  └── 否 → 无明确多数 → "Divided"
```

**场景示例：**

| 分布 | overall_bias | consensus_strength | consensus_type | 解读 |
|:----|:-----------:|:-----------------:|:-------------|:-----|
| 5:0:1 | +0.83 | 0.83 | Bullish | 群体强烈看涨 |
| 0:0:6 | 0.0 | 1.0 | Neutral | 全体谨慎观望 |
| 2:2:2 | 0.0 | 0.33 | Divided | 观点完全分裂 |
| 1:4:1 | -0.50 | 0.67 | Bearish | 群体偏悲观 |

---

## 自己试试（5 分钟）

1. 打开 `src/debate/orchestrator.py` 找到 `compute_bias_report` 函数
2. 运行测试：`python -m pytest tests/test_debate/test_bias_report.py -v`
3. 试三个场景的偏斜度：

```python
from src.debate.orchestrator import compute_bias_report

# 场景 1：牛市共识
r1 = compute_bias_report({"Bullish": 5, "Bearish": 1, "Neutral": 1})
print(f"偏斜度={r1.overall_bias}, 共识={r1.consensus_type}")

# 场景 2：全体观望
r2 = compute_bias_report({"Neutral": 5})
print(f"偏斜度={r2.overall_bias}, 共识={r2.consensus_type}")

# 场景 3：深度分歧
r3 = compute_bias_report({"Bullish": 3, "Bearish": 3})
print(f"偏斜度={r3.overall_bias}, 共识={r3.consensus_type}")
```

思考题：为什么 `exact_50_percent` 场景（3/6=0.5）被判定为 Divided 而不是 Bullish？

---

**上一篇：[21 工程纪律](21-engineering-discipline.md)** ← 链接

**下一篇：待编写**
