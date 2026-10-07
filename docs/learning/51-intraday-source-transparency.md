# 51 前端来源透明：单源可用不等于多源核验

## 延伸：引用存在不等于关系成立（2026-10-07）

`backend/sector_maps.py` 的地图生成结果与已审核静态图分开保存。
`validate_evidence` 能检查引用来自输入且原文确实存在，但不能证明模型推断在语义上成立。
所以 `frontend/components/sector/generated-map.tsx` 把所有节点、箭头标为 AI 推断，
点击可看原文，不能把“引用匹配”改成“供货关系已核实”。

`MapStore.save` 用 SQLite 事务追加版本；失败不删除上次成功图。资料哈希忽略读取时钟，
相同资料重复读取不再付费调用 AI。每份节选和公司样本上限必须在页面可见。

自己试试：生成 BK1325 地图并刷新，检查版本仍在；打开节点引用，对照解释是否超出原文；
阻断来源后再次更新，确认错误可见且旧版本保留。不要把“离线可看”理解成“离线仍自动追踪”。

## 一句话

> 行情有一条真实可用来源时可以继续展示，但必须把“只有谁在供数”持续写清楚；没有真实点时宁可留空，也不能画一条看起来合理的曲线。

---

## 为什么需要它？

### 问题场景

“接口成功”并不等于“多家数据一致”。如果东方财富失败而腾讯仍返回有效分钟点，直接把
页面锁死会损失时效性；如果仍显示“已验证”，又会把单源伪装成多源。更危险的是接口没点
时补一条示意曲线，使用者无法区分事实与设计稿。

### 它的解法

把两件事分开：`usable` 决定能不能展示真实数据，`verification_status` 决定如何披露证据
强度。单源和冲突不阻断真实曲线，但面板头部始终显示状态；详细诊断由使用者点击展开。

---

## 项目里的真实代码

打开 `frontend/lib/intraday-source-state.ts`：

```typescript
if (data?.usable && data.price_points.length > 0) return "usable";

case "single_source":
  return {
    label: `单一数据源 · ${canonicalSourceName(data) ?? "来源待确认"}`,
    detail: `未交叉验证 · ${time}`,
    tone: "warning",
  };
```

第一段只承认可用的真实价格点；第二段没有禁止图表，而是如实降低来源证明强度。
`frontend/components/stock/intraday-line-chart.tsx` 只把 `timestamp` 和 `close` 转成折线，
不会从一个价格推造 open/high/low。`IntradayBattlefieldPanel` 则负责网络错误、不可用、单源、
冲突和多源通过等用户可见状态。

---

## 和“失败即整页禁用”有什么不同？

| 对比 | 失败即禁用 | 来源透明降级 |
|:-----|:-----------|:-------------|
| 单源有效 | 页面不可用 | 继续展示，并提示未交叉验证 |
| 无真实点 | 容易被示意图填充 | 明确留空 |
| 出错归因 | 前端可能猜测数据商 | 只展示 API 返回的逐源诊断 |
| 使用者判断 | 只能信或不用 | 知道数据来自谁、强度如何 |

---

## 自己试试（5 分钟）

1. 打开 `frontend/tests/intraday-source-state.test.mts`。
2. 把 fixture 从 `single_source` 改成 `source_conflict`，运行 `pnpm --dir frontend test`。
3. 再把 `price_points` 清空，观察模式是否变成 `unavailable`。
4. 思考题：已有可用数据刷新失败时，为什么不应该立刻清空图？

---

**上一篇：[运行时证据怎样安全合流](50-runtime-evidence-assembly.md)**

**下一篇：待补充**
