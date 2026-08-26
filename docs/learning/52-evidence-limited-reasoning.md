# 52｜证据不完整时怎样继续推理而不伪装完整

## 一句话

> 缺数据不一定要停止 AI，但必须把“能推理”和“能交易”拆开：缺源可带限制推理，
> 冲突/损坏必须阻断，受限结果不能自动进入执行链。

---

## 为什么需要它？

### 问题场景

把所有不完整证据都当错误，会让某个新闻源短时不可用时整个研究功能停摆；完全忽略
缺口继续推理，又会生成看似完整的结论。真正需要区分的是三种状态：

| 状态 | 研究推理 | 风控/交易 | 例子 |
|:-----|:--------:|:---------:|:-----|
| 完整 | 允许 | 按正常门禁 | 两个独立来源均成功 |
| 不完整但未损坏 | 允许，必须标注 | 不允许自动进入 | 缺一个来源、陈旧、暂时失败 |
| 冲突或损坏 | 阻断 | 阻断 | 身份错误、未来时间、价格冲突 |

### 它的解法

项目用 `EvidenceLimitation` 把缺口作为结构化结果保存，而不是只在日志中警告。相同标注
同时注入市场简报、最终 `DebateResult`、摘要和记忆快照，因此任何下游都能知道这次
分析使用了有限证据。

LangGraph 在分析师、大师和评审结束后再次检查限制：有标注的研究结果可以返回用户，
但不进入风险官、交易员和 PM 节点。这比单纯降低置信度更可靠，因为置信度是模型判断，
证据完整性是输入事实，两者不能互相替代。

---

## 项目里的真实代码

打开 `src/debate/orchestrator.py`：

```python
if not quote_evidence_envelope.complete:
    if _must_block_reasoning(quote_evidence_envelope):
        return {
            "evidence_envelope": quote_evidence_envelope.model_dump(mode="json"),
            "errors": ["EVIDENCE_INCOMPLETE"],
        }
    evidence_limitations.append(
        _evidence_limitation(quote_evidence_envelope)
    )
```

这段代码先判断证据是否损坏。普通缺口转换成限制标注并继续，冲突、身份错乱或未来数据
仍走阻断路径。

推理结束后的执行隔离是：

```python
def _route_after_reasoning(state: DebateState) -> str:
    return "stop" if state.get("evidence_limitations", []) else "risk"
```

因此“给出有限分析”不等于“允许生成交易计划”。

---

## 和失败关闭有什么不同？

| 对比 | 全部失败关闭 | 本方案 |
|:-----|:-------------|:-------|
| 单源暂时失败 | 整个 AI 停止 | 继续推理并披露缺口 |
| 数据冲突 | 停止 | 仍然停止 |
| 用户能否看到限制 | 只看到失败 | 结果携带结构化限制 |
| 是否自动交易 | 不交易 | 受限结果仍不交易 |

---

## 自己试试（5 分钟）

1. 运行 `pytest tests/test_debate/test_orchestrator.py -q`；
2. 找到 `test_limited_evidence_runs_llm_but_does_not_enter_trade_chain`；
3. 把 `_route_after_reasoning()` 的判断删除，观察受限证据可能进入交易链；
4. 把来源状态改成 `CONFLICTED`，确认分析师和大师不再执行。

---

**上一篇：[50｜运行时证据怎样安全合流](50-runtime-evidence-assembly.md)**

**下一篇：** 待续
