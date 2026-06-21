---
department: 前端部
codebase: frontend/
last_updated: 2026-06-21
---

# 🎨 前端部工作交接

## 当前状态

### 模块完成度

| 子系统 | 状态 | 说明 |
|:-------|:----:|:------|
| 三页路由（首页→板块→个股） | ✅ | Next.js 16 App Router |
| 17 个功能组件 + 4 布局组件 | ✅ | 含 loading/error/empty/data 四态 |
| K 线真渲染（CandlestickChart） | ✅ | Lightweight Charts 成交量直方图 |
| 暗色主题系统 | ✅ | CSS 变量 + Tailwind, Bloomberg × TradingView 配色 |
| 搜索 autocomplete | ✅ | 防抖 300ms + useStockSearch hook |
| 4 Tab 面板（个股页） | ✅ | 辩论/技术指标/资金流向/信任度 |
| 离线检测 | ✅ | `useOnlineStatus()` + 全局离线横幅 |
| Error Boundary | ✅ | `error.tsx` + `not-found.tsx` |
| 全局状态 | ✅ | Zustand 面包屑 + 最近浏览 |

### 测试

| 检查项 | 结果 |
|:-------|:----:|
| `pnpm build` | ✅ 零错误 |
| TypeScript strict | ✅ 零 `any`、零 `@ts-ignore` |
| 前端 mock 数据 | ✅ 零造假 |

### 关键架构决策

- **React Server Component 架构**：页面级 Server Component 包装 Client Component
- **TanStack Query 数据获取**：所有 API 调用通过 hooks 封装，组件不直接 fetch
- **TypeScript 类型手动同步**：从 Pydantic 模型手导（待自动化）

---

## 开放债务

| ID | 描述 | 优先级 | 预估 |
|:---|:-----|:------:|:----:|
| TD-033 | capital-flow-panel.tsx `.reverse()` 变异数组违反不可变性 | 🟢 | 5min |

## 已关闭

| ID | 标题 | 修复日期 |
|:---|:-----|:--------|
| TD-025 | 全局 Error Boundary 缺失 | 2026-06-17 |
| TD-026 | 骨架屏永不消失 | 2026-06-17 |
| TD-027 | 无离线检测 | 2026-06-17 |
| TD-028 | 搜索无防抖 | 2026-06-17 |
| TD-029 | 死代码未清理 | 2026-06-17 |
| TD-030 | 资金流向绕过 Provider 层 | 2026-06-17 |
| TD-031 | 辩论轮询永不停止 | 2026-06-17 |

---

## 下一步优先级

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 🟢 | TD-033 修 `.reverse()` → `.toReversed()` | 无 |
| 2 🟢 | 浏览器端四态全量验证（拔网线/空数据/超时） | 无 |
| 3 🟢 | TypeScript 类型与 Pydantic 模型自动同步 | 后端 API 部 |

---

## 关键文件索引

| 文件 | 行数 | 说明 |
|:-----|:----:|:------|
| `frontend/app/page.tsx` | — | 宏观总览页 |
| `frontend/app/sector/[id]/page.tsx` | 134 | 板块分析页 |
| `frontend/app/stock/[code]/page.tsx` | 130 | 个股决策页（4 Tab） |
| `frontend/components/stock/candlestick-chart.tsx` | 138 | K 线图（Lightweight Charts） |
| `frontend/components/stock/debate-panel.tsx` | 191 | 辩论面板 |
| `frontend/components/stock/technical-indicators-panel.tsx` | 302 | 技术指标面板 |
| `frontend/components/stock/capital-flow-panel.tsx` | 134 | 资金流向面板（⚠️ TD-033） |
| `docs/06-departments/09-frontend/ROLE.md` | — | 👤 前端部角色定义 |
| `docs/06-departments/09-frontend/STANDARDS.md` | — | 📐 前端部技术规范 |
