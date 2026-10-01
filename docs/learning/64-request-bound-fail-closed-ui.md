# 64｜异步结果必须绑定当前请求

> 一句话：新的异步分析一旦开始，旧结果就必须先失效；只有请求身份匹配且本次无错误、
> 无超时的结果，才允许继续显示。

## 为什么需要它？

投资分析页面最危险的状态不是“报错”，而是“报错旁边仍有一份看起来完整的旧建议”。
如果 hook 只在新请求成功后替换 `sessionId`，那么新请求失败时，React Query 仍能按旧查询键
返回上一次结果。用户很容易把旧共识误认成本次分析。

安全状态机必须满足三条不变量：

1. `start` 立即把 `sessionId` 设为 `null`，不等待网络结果；
2. `failed` 仍保持空 session，绝不恢复上一次成功值；
3. 展示层同时校验当前 session、查询错误和超时，任何一项不满足都不渲染结果。

## 项目里的真实代码

打开 `frontend/lib/debate-session.ts`：

```ts
export function debateRequestReducer(state, action) {
  switch (action.type) {
    case "start":
      return { sessionId: null, running: true };
    case "succeeded":
      return { sessionId: action.sessionId, running: false };
    case "failed":
      return INITIAL_DEBATE_REQUEST_STATE;
  }
}
```

`frontend/lib/hooks/use-debate.ts` 直接使用这个 reducer，所以测试的不是一份脱离产品的伪模型。
轮询计数也被抽成纯函数：有结果立即停止；第 60 次仍无结果时返回明确 `timedOut`，供界面
显示“未生成新的投资结论”。

打开 `frontend/components/stock/debate-panel.tsx`，结果渲染还要通过身份校验：

```ts
const results = !visibleError
  && !running
  && sessionId
  && debateResult?.session_id === sessionId
  && debateResult.vote_summary
    ? { voteSummary: debateResult.vote_summary, analyses: debateResult.analyses ?? [] }
    : null;
```

这里的关键不是多写几个 `if`，而是默认拒绝展示，只有所有安全条件都成立才放行。

## 请求时间不等于证据时间

前端可以知道“什么时候收到结果”，但这不代表行情、新闻或财务证据的采集时间。当前
`DebateResult` API 还没有稳定的证据时间字段，因此本次只展示真实请求 ID，没有把浏览器
时间伪装成证据时间。证据时间应由 FW-020 后端契约提供，再由前端原样展示。

## 自己试试（5 分钟）

1. 运行 `cd frontend && pnpm test`；
2. 找到“新辩论开始时立即解除旧 session”测试，把 `start` 分支改成保留旧 ID；
3. 再运行测试，观察陈旧结果保护用例立即失败；
4. 思考：如果只在组件里隐藏结果、但 hook 仍保留旧 session，其他复用该 hook 的组件会怎样？

---

**上一篇：[50｜运行时证据怎样安全合流](50-runtime-evidence-assembly.md)**

**下一篇：[52｜证据不完整时怎样继续推理而不伪装完整](52-evidence-limited-reasoning.md)**
