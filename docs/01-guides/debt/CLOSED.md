# 🗄️ 已关闭债务

> 历史已修复债务，保留以供参考。

---

## 代码实现（💻）

| ID | 标题 | 关闭日期 | 修复说明 |
|:---|:-----|:--------|:---------|
| TD-002 | AgentResult 缺泛型 | 2026-06-07 | Pydantic BaseModel + Generic[T]，88 tests 验证 |
| TD-012 | LLM 参数硬编码 | 2026-06-07 | LLMConfig + 接口修改 + 17 测试，202 全量通过 |
| TD-013 | 缺少 streaming 接口 | 2026-06-08 | `LLMService.astream()` + 6 测试，228 全量通过 |
| TD-015 | 缓存不支持多配置 | 2026-06-08 | 非默认 LLMConfig 不缓存（与 TD-012 同步修复） |
| TD-020 | 后端板块/产业链数据增强层缺失 | 2026-06-17 | market.py 重写 — heat/chain_map/ai_analysis/ai_rating 全面板真实数据 |
| TD-021 | 16 处 `except Exception: pass` 静默吞异常 | 2026-06-17 | 全部改为 `logger.warning()`，16 块全覆盖 |
| TD-022 | `collect_data_node` 变量未初始化 | 2026-06-17 | 代码已有初始化，无需修改 |
| TD-023 | 后端 API 全返回 HTTP 200 | 2026-06-17 | trust.py→503，debate.py→500，前端 TanStack Query 自动识别 |
| TD-024 | 数据源调用无超时 | 2026-06-17 | `backend/async_utils.py` 15s 超时 + `asyncio.to_thread()` |
| TD-025 | 前端无 Error Boundary | 2026-06-17 | `error.tsx` + `not-found.tsx` |
| TD-026 | 骨架屏永不消失 | 2026-06-17 | page.tsx 四态分离（loading/error/empty/data） |
| TD-027 | 前端无离线检测 | 2026-06-17 | `useOnlineStatus()` + 全局离线横幅 |
| TD-028 | 前端搜索无防抖 | 2026-06-17 | `useDebounce(query, 300)` 通用 hook + useStockSearch 接入，pnpm build 通过 |
| TD-029 | 前端死代码清理 | 2026-06-17 | 删 `components/layout/` (5文件) + `stores/` (2文件) + `hot-news.tsx` + echarts/zustand 依赖 |
| TD-030 | 资金流向绕过 Provider 层 | 2026-06-17 | CapitalFlowItem 迁移 models.py → DataSource Protocol 扩展 → 三源实现 → FallbackSource → DataCollector 缓存+健康监控 → backend 路由切换 |
| TD-031 | 辩论轮询永不停止 | 2026-06-17 | `useRef` 计数 + 最大 60 次（~120s）兜底停止条件 |

## 架构设计（🏛️）

| ID | 标题 | 关闭日期 | 修复说明 |
|:---|:-----|:--------|:---------|
| TD-014 | AgentContext 缺辩论槽位 | 2026-06-07 | +3 字段 +7 测试，185 全量通过 |
| TD-016 | LangGraph 零使用未验证 | 2026-06-08 | 最小原型 20 测试，222 全量通过 |

## 基础设施（⚙️）

| ID | 标题 | 关闭日期 | 修复说明 |
|:---|:-----|:--------|:---------|
| TD-009 | CI 迁移 GitHub Actions | 2026-06-06 | 创建 `.github/workflows/ci.yml`，双版本验证 |
| TD-011 | Pyright extraPaths 硬编码 | 2026-06-05 | 移除硬编码路径，`pip install -e .` 自动识别 |

## 文档（📝）

| ID | 标题 | 关闭日期 | 修复说明 |
|:---|:-----|:--------|:---------|
| TD-010 | README 仍为 Gitee 模板 | 2026-06-08 | README.en.md 替换为实际项目介绍 |
