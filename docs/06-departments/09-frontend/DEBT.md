---
department: 前端部
---

# 🐛 前端部债务清单

> 本文件只列前端部（`frontend/`）的债务。

---

## 开放债务

| ID | 标题 | 严重度 | 类型 | 状态 |
|:---|:-----|:------:|:----|:----|
| — | 当前无开放前端债务 | — | — | ✅ |

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
| TD-033 | capital-flow-panel.tsx `.reverse()` 变异数组 | 2026-08-21 | 当前实现使用 `slice(-10)`，不再就地反转来源数组；引用同步清理 |
| TD-077 | Next.js 16 已移除 `next lint` | 2026-08-21 | 迁移 ESLint 9 flat config；本地检查与 GitHub CI 均设为零警告阻塞门禁 |
