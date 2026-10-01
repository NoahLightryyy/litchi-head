# 62 决策血缘失败关闭：有分数，不等于可验证

## 一句话

> 投资决策只有同时绑定原始观点、模型/Prompt/配置/代码版本、证据哈希和决策时间，才
> 能进入效果样本；缺一项就明确排除，而不是猜值或补零。

---

## 为什么需要它？

### 问题场景

一条旧辩论记录可能有 `weighted_score=80` 和 `confidence=0.8`，看起来足以跟用户收益
比较。但如果不知道它使用了哪个模型、哪版 Prompt、哪些点时证据，结果就不可复现；
如果失败的 Agent 被默认成 0，它还会悄悄改变完整分母。

### 它的解法

`verify_ai_decision_reference()` 采用失败关闭：只有所有必要信号都存在且一致时才返回
`eligible`。核验结果是新的不可变事实，不修改原用户操作。这样旧记录仍可展示，
但不会污染置信度校准、Agent 权重或真钱扩大依据。

---

## 项目里的真实代码

打开 `src/retro/ai_decision_reference.py`：

```python
if summary.weighted_score <= 0:
    reasons.add(DecisionReferenceReason.WEIGHTED_SCORE_MISSING_OR_ZERO)
if failed:
    reasons.add(DecisionReferenceReason.AGENT_FAILURE_PRESENT)
if provenance is None:
    reasons.add(DecisionReferenceReason.DECISION_PROVENANCE_MISSING)

eligible = not ordered_reasons and provenance is not None
```

`session_snapshot_sha256` 绑定完整会话信封，`original_viewpoints_sha256` 单独绑定所有
Agent 原始观点；`AiDecisionReferenceLedger` 用确定性 reference ID 幂等追加，发现同 ID
不同事实时拒绝写入。

---

## 和“保存一个 decision_id”有什么不同？

| 对比 | 只有 ID | 不可变血缘引用 |
|:-----|:--------|:---------------|
| 能否知道内容后来被改过 | 不能 | session SHA-256 会变化 |
| 能否复现模型和 Prompt | 不能 | 明确版本覆盖每个成功 Agent |
| 失败/零值处理 | 容易被当默认值 | 原因码失败关闭 |
| 是否改写用户操作 | 常见做法是更新状态 | 另追加核验事实 |

---

## 面试会怎么问

> **Q: 为什么不能把缺失置信度当成 0？**
>
> A: “模型明确给出 0”与“字段没采集到”是两种事实。混在一起会扭曲分布、完整分母和
> 校准结果。应保留缺失，并用资格门禁把不可验证样本排除。

---

## 自己试试（5 分钟）

1. 打开 `tests/test_retro/test_ai_decision_reference.py`。
2. 运行 `python -m pytest tests/test_retro/test_ai_decision_reference.py -q`。
3. 删除测试 provenance 中一个 Agent 的 Prompt 版本，观察原因码变为
   `prompt_version_missing`；思考为什么这比抛一个通用异常更利于审计。

---

**上一篇：[不可变用户操作账本](61-immutable-user-action-ledger.md)**

**下一篇：待续**
