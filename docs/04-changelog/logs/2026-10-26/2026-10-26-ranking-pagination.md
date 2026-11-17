# 2026-10-26 搜索页排行榜每页10条

用户明确要求排行榜按10条分页。恢复时工作树 `codex/market-availability` 的HEAD为7eb8183，
会话校验MATCH，交叉读取Git、HANDOVER和最新ETF日志；原项目目录未修改。

## 实现

- `ranking-page.ts` 和 `ranking-pagination.tsx` 共用切片与按钮，保留全榜顺序和全部条目。
- 个股涨幅、同花顺资金、折叠的东方财富资金榜各自分页；周期或口径切换重置到第一页。
- 数据缩短后页码限制在有效范围；空榜无分页；刷新失败保留的数据仍可翻页。
- 仅前端展示，无新API字段、来源或LLM调用；来源前20／前50与每页10条分别表述。

## 验证

- 专项10项通过，前端全量202项通过，TypeScript通过。
- 浏览器真实缓存涨幅榜20项和同花顺50项均每页10项；两榜分别翻第2页显示11–20，
  涨幅榜末页禁用下一页；同花顺切周期再返回，恢复第1页，涨幅榜仍在第2页。
- `python scripts/check.py --diff 7eb8183` 6/6通过：Ruff、Pyright（0错误／警告）、README同步、
  前端ESLint和TypeScript；本次纯前端改动按检查器规则跳过Python测试，前端测试另行执行202项全过。
- `git diff --check` 通过；浏览器截图保存在本机 `/tmp/litchi-ranking-pagination.jpg`。

## 五同步

SPEC与部门HANDOVER同步；既有学习卡57补充查询身份与分页状态。
FW-RANKING-PAGING-001登记即关闭，开放债务数不变。
引用清理覆盖三个排行榜，旧全量map改为分页items；未改变后端查询条数及范围说明。
没有推送或合并来源工作树。
