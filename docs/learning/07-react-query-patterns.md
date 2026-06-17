# 08 React Query 模式：防抖与轮询兜底

## 一句话

> 用 `useDebounce` 防止搜索高频打后端，用 `refetchInterval`+`useRef` 给轮询设兜底停止条件。

---

## 为什么需要它？

### 问题场景

**场景 A：搜索框高频请求**

用户在搜索框输入"贵州茅台"时，每按一个字母都触发 API 请求：
```
贵 → GET /search?q=贵
贵州 → GET /search?q=贵州      ✗ 中间态，浪费
贵州茅 → GET /search?q=贵州茅   ✗ 中间态，浪费
贵州茅台 → GET /search?q=贵州茅台  ✓ 用户最终想要的
```
输入 4 个字符发了 4 个请求，中间 3 个是浪费的。

**场景 B：轮询永不停止**

辩论引擎启动后，前端每 2 秒轮询结果。如果后端挂了或返回异常，轮询永远不停——用户不关页面就一直发请求。

### 它的解法

**防抖**：等用户停止输入 300ms 后再发请求。无论用户多快敲键盘，只发一次。

**轮询兜底**：用计数器记录轮询次数，超过上限（60 次 ≈ 120 秒）自动停，不让轮询无限跑。

---

## 项目里的真实代码

### 1. useDebounce 通用 Hook

打开 `frontend/lib/hooks/use-debounce.ts`：

```typescript
import { useState, useEffect } from "react";

export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);  // 关键：每次 value 变，取消上一次定时
  }, [value, delay]);

  return debouncedValue;
}
```

**解读**：
- 每次 `value` 变化 → 设一个 `delay` 毫秒的定时器
- 如果 `delay` 毫秒内 `value` 又变了 → `clearTimeout` 取消旧定时器，设新的
- 只有用户稳定 `delay` 毫秒不输入，才返回最新值
- 这叫做"leading-edge debounce"（总是在末尾触发）

### 2. 接入搜索 Hook

打开 `frontend/lib/hooks/use-stock.ts`：

```typescript
export function useStockSearch(query: string) {
  const debouncedQuery = useDebounce(query, 300);        // ← 300ms 防抖
  return useQuery({
    queryKey: ["stocks", "search", debouncedQuery],       // ← 用防抖后的值
    queryFn: () => searchStocks(debouncedQuery),
    enabled: debouncedQuery.length >= 2,                   // ← 至少 2 字符才查
    staleTime: 60_000,                                     // ← 60s 内同结果不重查
  });
}
```

**数据流**：
```
用户输入 → setSearchQuery → useDebounce 300ms → 防抖后的值 → useQuery → API
```

### 3. 轮询兜底

打开 `frontend/lib/hooks/use-debate.ts`：

```typescript
export function useDebateResult(sessionId: string | null) {
  const pollCountRef = useRef(0);
  const MAX_POLLS = 60;   // ≈ 120 秒兜底

  return useQuery({
    queryKey: ["debate", "result", sessionId],
    queryFn: () => fetchDebateResult(sessionId!),
    enabled: !!sessionId,
    refetchInterval: (query) => {
      const data = query.state.data as DebateResult | undefined;

      // 条件 1：辩论完成 → 停
      if (data?.vote_summary) return false;

      // 条件 2：超过最大轮询次数 → 停
      pollCountRef.current += 1;
      if (pollCountRef.current >= MAX_POLLS) return false;

      return 2000;  // 继续轮询，2 秒一次
    },
    staleTime: Infinity,
  });
}
```

**解读**：
- `useRef` 存计数器——组件重新渲染时不丢失
- `refetchInterval` 可以是函数，返回 `false` 停，返回数字继续
- 两个停止条件互为兜底：`vote_summary` 来了正常停，后端挂了 120 秒后强制停
- `staleTime: Infinity` 防止结果回来后因组件重渲染重新查

---

## 和 setInterval / clearInterval 有什么不同？

| 对比 | setInterval 传统方案 | React Query 方案 |
|:-----|:--------------------|:-----------------|
| 生命周期管理 | 手动 mount/unmount | 自动绑定 query 生命周期 |
| 条件停止 | 手动 `if() clearInterval()` | `refetchInterval` 返回 `false` |
| 请求去重 | 人工加 flag | `queryKey` 自动去重 |
| 组件卸载 | 必须在 `useEffect cleanup` 清理 | 自动停止 |
| 缓存 | 没有 | `staleTime` / `gcTime` 内置 |

---

## 面试会怎么问

> **Q: 防抖和节流有什么区别？**
>
> A: 防抖（debounce）——等用户"停下"才执行，适用于搜索输入。
> 节流（throttle）——保证固定频率执行一次，适用于滚动事件。
> 实现上：防抖每次重置定时器，节流第一次设定时器后不再重置。

> **Q: React Query 的 refetchInterval 返回 false 和返回 0 有什么区别？**
>
> A: 返回 `false` 彻底停止自动轮询，`refetchInterval` 函数不再被调用。
> 返回 `0` 也会停，但语义上 `0` 表示"无穷快"而不是"停"，官方推荐用 `false`。

> **Q: useRef 和 useState 在计数场景的区别？**
>
> A: `useRef` 修改不触发重渲染，适合计数器。
> `useState` 修改触发重渲染，如果`refetchInterval`里的计数器用了 `useState`，每次+1都会重渲染组件，浪费性能。

---

## 自己试试（5 分钟）

1. 打开 `frontend/lib/hooks/use-debounce.ts`，把 `300` 改成 `1000`，在搜索框输入"平安银行"——看看是不是延迟 1 秒才出结果？
2. 打开 `frontend/lib/hooks/use-debate.ts`，把 `MAX_POLLS` 改成 `3`，触发辩论后看 Network 面板——3 次后请求是否停止？
3. 想一想：为什么 `refetchInterval` 里用 `useRef` 而不是 `useState`？把 `pollCountRef` 改成 `const [pollCount, setPollCount] = useState(0)` 会出什么问题？

---

**上一篇：[06 技术指标计算](06-technical-indicators.md)**

**下一篇：[08 类型注解与 Pyright](08-type-hints-pyright.md)**
