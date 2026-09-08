# 57 可访问的数据视图：状态准确还不够，操作也必须可达

## 一句话

> 数据页面要同时做到状态互斥、空态可见和键盘可操作，否则“画面能看”不等于用户真的能用。

---

## 为什么需要它？

### 问题场景

请求失败与业务空结果如果共用一个分支，用户会把“暂时取不到数据”误认为“这个对象不存在”；
相反，空数组直接渲染成空表格，也会让用户误以为页面坏了。

表格行的 `onClick` 还有另一个隐患：鼠标可以点击，但键盘不能聚焦，浏览器也无法提供原生
链接的打开新标签页、复制地址和访问历史语义。

### 它的解法

先用纯函数把查询状态归一为 `loading / error / empty / data` 四种互斥模式，再由页面只渲染
对应分支。纯函数不依赖 React，可以用低成本消费者测试锁定优先级。

导航则使用真正的 `<Link>`，把焦点样式和可访问名称放在链接上；布局用移动优先的单列，
只在宽屏恢复多列。

---

## 项目里的真实代码

打开 `frontend/lib/sector-detail-view.ts`：

```ts
export function resolveSectorDetailViewMode({ sector, isLoading, isError }) {
  if (isLoading) return "loading";
  if (isError) return "error";
  if (!sector) return "empty";
  return "data";
}
```

打开 `frontend/components/sector/stock-list.tsx`：

```tsx
<Link
  href={`/stock/${s.code}`}
  className="flex flex-col rounded-sm focus-visible:ring-2 focus-visible:ring-accent-blue"
  aria-label={`查看 ${s.name}（${s.code}）的个股决策`}
>
  <span>{s.name}</span>
  <span>{s.code}</span>
</Link>
```

第一段把状态判断从 JSX 中抽离，第二段让导航恢复浏览器原生能力。页面加载容器还使用
`role="status"` 和 `aria-busy="true"`，请求失败区域使用 `role="alert"`。

---

## 和“整行 onClick”有什么不同？

| 对比 | `tr onClick` | 原生链接 |
|:-----|:-------------|:---------|
| 键盘聚焦 | 默认不可达 | 原生可达 |
| 打开新标签页 | 需另写逻辑 | 浏览器原生支持 |
| 语义 | 只是带点击事件的行 | 明确是导航 |
| 焦点提示 | 容易遗漏 | 可用 `focus-visible` 明示 |

---

## 面试会怎么问

> **Q: 为什么不只检查 `data` 是否存在来决定页面状态？**
>
> A: 因为 `data` 缺失可能表示仍在加载、请求失败、查询被禁用或业务空结果。应先按查询生命周期
> 判定 loading/error，再判断业务 empty，最后才进入 data，避免状态互相冒充。

---

## 自己试试（5 分钟）

1. 打开 `frontend/app/sector/[id]/page.tsx`，找出四个页面模式；
2. 在浏览器中只用 Tab 键聚焦一个板块个股链接并按 Enter；
3. 把测试样本的 `stocks` 和 `chain_map` 设为空，确认页面显示空态而不是空白；
4. 思考题：后台刷新失败但已有旧数据时，应该新增哪一种 `stale` 表示？

---

**上一篇：[健康检查分层：连得上不等于有数据](56-layered-health-contract.md)**

**下一篇：[58｜同步上游并发](58-bounded-sync-upstream-concurrency.md)**


## 首页大列表与样式层（2026-09-04）

`sector-ranking.tsx` 首屏渲染10条，按钮每次增加10条，并显示“显示N/总数”。排序与收起重置可见数量和表格滚动位置，不修改上游排序或补造行。`sector-ranking-view.ts` 的涨跌条按全榜最大绝对涨跌幅共享比例，零在中线；数值始终保留，颜色不是唯一信息。

全局 `* { padding: 0; margin: 0 }` 若不放入CSS层，会盖过Tailwind在utilities层中的间距。`globals.css` 将reset放入 `@layer base`，浏览器main的p-6从0恢复24px。

自己试试：用1000条明确标记的测试数据挂载组件，检查10→20→10行、键盘收起与scrollTop=0；然后检查main的computed padding。测试数据不能放进真实行情接口。独立验收页退出后删除，并清理其Next开发类型缓存，防止生产构建继续引用已删除的测试路由。

## 真实快照接线（2026-09-05）

接口返回partial不代表没有数据：保留data并披露limitations。`market-contract.ts`校验category、带时区as_of、source和延迟标志，`sector-ranking.tsx`仅按后端category显示行业/概念。上游f62为元，后端HTTP固定亿元，前端只格式化；重复除1e8与忘记转换同样危险。真实浏览器验收必须覆盖10→20→10、实际排序和时间旁注，不能用合成组件测试代替端到端恢复。

## 分页替代追加（2026-09-05）

`sectorPage`先过滤全榜再切片，每页10条，页数至少1且请求页码夹紧。搜索不能只搜当前10条，否则远处板块会被误判不存在；刷新导致条目数变少时，夹紧页码避免空白尾页。搜索/排序回第一页，页内保持上游rank。自己试试：跳尾页，搜索bk1629，再清空；确认搜索结果与页码都正确。

## 缺时间先核对原始响应（2026-09-05）

AKShare对财新响应只选择tag/summary/url，原始time被投影丢失。`caixin_news.py`保留原始Unix秒，明确转上海时区；不能把“包装库未返回”直接判断为“来源没有”。自己试试：对照适配器测试1788569539与2026-09-05T08:52:19+08:00，删除time确认null与partial仍保留。

## 详情失败与不存在（2026-09-07）

只在404且错误码MARKET_SECTOR_NOT_FOUND时显示不存在，503与网络错误应显示失败。后台刷新失败仍保留旧数据并提示；手动refetch避免整页重载，retry:false避免15秒上游截止被自动重试倍增。首页成功不能替代详情验收，必须真实点击到详情检查成分股。

## 证据图谱的边界（2026-09-07）

`src/data/chain_evidence.py`把industry_activity和company分开：官方行业分层证据不能证明公司供货关系。每个节点和边都引用原始来源；URL、日期和原文定位帮助用户复核。校验器只验证结构，不替代事实审核。自己试试：把候选行业节点连成supplies边，运行test_chain_evidence，确认被拒绝。

## 来源跟随节点（2026-09-08）

`chain-map.tsx`使用原生details/summary展开原文链接、发布/核验日期和页码。目录无edges时不自动添加箭头；只有明确记录的industry_sequence才展示产业顺序。消费者校验身份、URL、日期和引用，后端目录损坏附CHAIN_EVIDENCE_INVALID并保留行情。自己试试：在BK1629展开基础层依据，再在BK1650对照子链范围和历史年份。

## 图与详情分离（2026-09-08）

产业链图把节点和真实边作为button，使用aria-pressed报告选中状态、aria-controls关联统一详情区。SVG只承载视觉连线并aria-hidden；键盘用户可用Enter选择同一关系。来源只在详情区展开，既减少重复也保留出处。自己试试：选择第二条箭头后展开依据，再用Enter选系统层，检查标题与来源同步切换。

## 分类不是评级

stock-list先对全量成分股进行名称/代码、涨跌正负零与资金正负零未知的交集筛选，再排序分页。null不能算资金零值。只暴露已有事实维度，不能把行情筛选命名综合评级。自己试试：选下跌且净流入，跳尾页，再搜索单只股票，确认页码重置和筛选仍同时生效。
