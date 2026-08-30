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

**下一篇：待补充**
