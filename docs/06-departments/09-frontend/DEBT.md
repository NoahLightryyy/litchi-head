---
department: 前端部
---

# 🐛 前端部债务清单

> 本文件只列前端部（`frontend/`）的债务。

---

## 开放债务

| ID | 标题 | 严重度 | 类型 | 状态 |
|:---|:-----|:------:|:----|:----|
| TD-033 | capital-flow-panel.tsx `.reverse()` 变异数组 | 🟢 low | 代码质量 | 📋 待评估 |
| TD-077 | Next.js 16 已移除 `next lint`，前端 lint 脚本失效 | 🟢 low | 构建工具 | 🆕 待评估 |

###### TD-077 Next.js 16 已移除 `next lint`，前端 lint 脚本失效

| 属性 | 值 |
|------|-----|
| **分类** | `构建工具` `severity:low` `module:frontend` `impact:CI` |
| **发现日期** | 2026-08-21 |
| **发现人** | AI 审视 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼30min |
| **日利息** | 开发者单独执行 `pnpm lint` 会失败，降低前端本地闸门可信度 |
| **实盘影响** | 不影响运行时行情展示，但可能让后续前端静态问题更晚被发现 |
| **触发场景** | 在当前 Next.js 16 依赖下运行 `pnpm --dir frontend lint` |
| **用户能发现吗** | 终端会明确报错；网页用户通常无法直接发现 |

**描述**：`frontend/package.json` 仍配置 `next lint`，但 Next.js 16 已移除该命令。
本轮继续以 TypeScript、Node tests、生产构建和项目检查脚本作为交付闸门。

**修复方向**：引入 ESLint CLI 与 Next.js 推荐配置，将 `lint` 脚本改为直接运行 ESLint，
再接入 `scripts/check.py`。

## 已关闭债务

| ID | 标题 | 修复日期 | 修复说明 |
|:---|:-----|:--------|:---------|
| TD-025 | 前端无全局 Error Boundary | 2026-06-17 | error.tsx + not-found.tsx |
| TD-026 | 骨架屏永不消失 | 2026-06-17 | page.tsx 四态分离 |
| TD-027 | 前端无离线检测 | 2026-06-17 | useOnlineStatus() + 离线横幅 |
| TD-028 | 前端搜索无防抖 | 2026-06-17 | useDebounce(query, 300) |
| TD-029 | 前端死代码未清理 | 2026-06-17 | 删 5 layout + 2 stores + echases/zustand |
| TD-030 | 资金流向绕过 Provider 层 | 2026-06-17 | 全链路贯通 |
| TD-031 | 辩论轮询永不停止 | 2026-06-17 | useRef 计数 + 最大 60 次 |
