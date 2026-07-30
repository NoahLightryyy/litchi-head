# 📐 前端部技术规范

> 扩展 [coding-style.md](../../01-guides/WORKFLOW.md#1-核心原则) 的前端特定规范。

---

## 代码规范

### 组件四态模式

每个数据驱动组件必须实现以下四种状态：

```tsx
// ✅ 正确：四态完备
function StockQuote({ code }: { code: string }) {
  const { data, isLoading, isError, error } = useQuery(...)
  
  if (isLoading) return <Skeleton className="h-24 w-full" />     // loading
  if (isError) return <ErrorState message={error.message} />      // error
  if (!data) return <EmptyState message="暂无行情数据" />          // empty
  return <QuoteContent data={data} />                              // data
}

// ❌ 禁止：只覆盖 data 状态
function StockQuote({ code }: { code: string }) {
  const { data } = useQuery(...)
  return <QuoteContent data={data!} />  // data 可能为空！
}
```

### TypeScript 类型

```tsx
// ✅ 正确：严格类型，零 any
interface StockQuoteProps {
  code: string
  price: number
  changePct: number
  volume: number
  fetchedAt?: string
}

// ❌ 禁止：使用 any
interface StockQuoteProps {
  code: any      // 禁止
  data: any      // 禁止
}

// ❌ 禁止：@ts-ignore / @ts-expect-error
// @ts-ignore  // 禁止
const price = data.price
```

### Mock 数据红线

```tsx
// ❌ 禁止：前端硬编码 mock 数据
const MOCK_QUOTES = [
  { code: "000001", price: 12.34 },  // 禁止！
]

// ✅ 正确：从后端 API 获取真实数据
const { data } = useQuery({
  queryKey: ["quote", code],
  queryFn: () => fetchStockQuote(code),
})

// ✅ 如果开发时需要 mock，用 MSW 或 TanStack Query DevTools
```

### 盘中 K 线展示

- `FINAL_DAILY` 与 `PROVISIONAL` 必须有可见文字标签；
- 今日动态 K 显示“盘中形成中”和 `as_of`，不能伪装成已收盘蜡烛；
- 正式指标与含盘中估算指标必须明确区分；
- 当日日 K 未收盘时 AI 按钮保持可用，不提示用户等待收盘；
- 证据失败时展示缺失层与重试建议，不用旧结论冒充本次分析。
- 明示“原始/前复权/后复权”、复权基准日和 `as_of`；默认技术图使用统一点时前复权；
- 当前价、订单参考价和价格轴上的可交易标记使用 RAW/实时价格，不能把后复权价
  当作当前价格；
- RAW 冲突、复权冲突、独立上游不足必须使用不同文案和状态，不只显示“加载失败”；
- 北交所缺第二源时显示“日线证据不足，AI 未启动”，不能降级成单源绿灯；
- 状态不能只靠红绿颜色表达，必须有文字、图标或可访问标签。

---

## 文件大小红线

| 文件 | 当前行数 | 红线 | 状态 |
|:-----|:--------:|:----:|:----:|
| 组件文件 | 最大 302（technical-indicators-panel）| **400** | ✅ |
| 页面文件 | 最大 134（sector/[id]）| **500** | ✅ |
| hooks 封装 | — | **200** | ✅ |

---

## 测试规范

### 必须覆盖的场景

- ✅ 每个组件正常渲染（data 状态）
- ✅ loading 骨架屏渲染
- ✅ error 状态显示错误消息
- ✅ empty 状态显示空提示
- ✅ 离线横幅显示
- ✅ 搜索防抖（300ms 延迟）

### 覆盖手段

| 场景 | 方法 |
|:-----|:------|
| 组件渲染 | `pnpm build` 零错误 |
| 数据流 | TanStack Query DevTools 验证 |
| 离线测试 | 拔网线 + 浏览器 DevTools Network |
| 四态测试 | 后端 mock 返回各状态响应 |
| 移动端 | 浏览器 DevTools 响应式模式 |

---

## 性能标准

| 指标 | 目标 | 测量方法 |
|:-----|:----:|:---------|
| 首次渲染（FCP） | ≤ 2s | Lighthouse |
| 页面加载（LCP） | ≤ 3s | Lighthouse |
| API 响应渲染 | ≤ 500ms（从数据到显示）| React DevTools Profiler |
| 构建体积 | ≤ 500KB（首屏 JS）| `pnpm build` 输出 |
| 图片/图标 | 懒加载 | Lighthouse |

---

## Git 规范

| 文件 | 应该提交 | 禁止提交 |
|:-----|:---------|:---------|
| `frontend/.env` | ❌ | ✅ `.gitignore` 已忽略 |
| `frontend/.next/` | ❌ | ✅ 构建产物 |
| `frontend/node_modules/` | ❌ | ✅ |
| `frontend/package.json` | ✅ | — |
| `frontend/tsconfig.json` | ✅ | — |
| `frontend/tailwind.config.ts` | ✅ | — |

---

## 审查清单

- [ ] 零 `any` 类型？
- [ ] 零 `@ts-ignore` / `@ts-expect-error`？
- [ ] 零前端 mock 数据？
- [ ] `pnpm build` 通过？
- [ ] 每个组件四态完备？
- [ ] 离线横幅已实现？
- [ ] hooks 封装了所有 API 调用（组件不直接 fetch）？
- [ ] 文件 ≤ 400 行？
- [ ] `.next` / `node_modules` 未提交？
- [ ] K 线口径、基准日、时间和证据状态是否用户可见？
- [ ] RAW/复权/独立源三类错误是否能被用户区分？
