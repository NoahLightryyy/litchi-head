# 56 健康检查分层：连得上不等于有数据

## 一句话

> 进程连通、数据源请求成功和业务数据可用是三个不同事实，不能用一个绿色状态代替。

## 为什么需要它？

前端曾请求不存在的 `/api/health/diagnose`：基础健康接口成功，详细诊断却 404，页面因此
长期显示“诊断信息暂不可用”。即使改用真实接口，后端也必须把空业务结果与成功分开统计。

解法是分层：先用 `/api/health` 判断服务是否在线，再校验 `/api/health/data-source` 的真实
响应契约并转换为 UI 状态。解析失败时降级显示，绝不猜测。

## 项目里的真实代码

打开 `src/data/collector.py`：`begin_batch()` 在上游请求前分配序号，
`record_batch()` 持锁一次性记录三指数结果，再按失败、空数据、成功的优先级归并当前健康。
晚到旧批仍计入历史，但不能覆盖更新批的当前状态；`snapshot()` 持同一锁读取一致快照。

前端来源故障判断（`frontend/lib/backend-health.ts`；业务可用性归类见下方备用源补充）：

```typescript
const degraded = value.status !== "ok" || summary.failing_endpoints > 0
  || summary.empty_endpoints > 0;
// 单项只读 current_status；禁止用 failures / total_failures 的历史值判断当前故障。
```

失败后恢复不能删除历史，也不能让历史累计值永久维持红灯。一个来源承担多个指数时，
后两个成功更不能抹掉第一个失败。测试见 `tests/test_data/test_health_recovery.py` 和
`tests/test_data/test_index_quote_runtime.py`。当前状态是最后一次完成的观察，不是实时可达保证。

## 自己试试（5 分钟）

1. 访问 `/api/health`，确认它只证明后端进程在线。
2. 访问 `/api/health/data-source`，把 `failing_endpoints` 临时改为 1 写进单元测试。
3. 运行 `pytest tests/test_data/test_health_recovery.py -q`，观察失败后恢复仍保留 failures。
4. 思考题：HTTP 200 但 `data: []` 应该算传输成功还是业务可用？

---

**上一篇：[55｜多源汇总不是把两个数字取平均](55-multi-source-index-reconciliation.md)**

**下一篇：[57｜可访问的数据视图](57-accessible-stateful-data-view.md)**

## 前端恢复消费（2026-09-04）

`frontend/lib/backend-health.ts` 严格消费 current_status；历史 failures 保留也不会让 healthy 继续告警。未知状态返回诊断不可用。消费者测试覆盖恢复、空结果和混合来源。指数卡消费 display_source，冲突提示与请求失败分开，不遮挡有效单源数据。



## 延伸：快照缓存不等于实时数据

候选 `src/data/providers/eastmoney_boards.py` 将 `as_of`（上游数据时间）、
`fetched_at`（完整采集时间）、`cached`（本次是否复用本地缓存）分别保存。
可能延迟的东方财富快照始终标记 `possibly_delayed=true`；缓存命中更快不代表报价更新。
只有页数/总量/唯一代码检查通过的完整数据才进入30秒缓存，过期后网络失败不返回旧缓存。

自己试试：运行 `pytest tests/test_data/test_eastmoney_boards.py -q`，对照缓存边界测试的
29.9秒和30秒，观察缓存命中与失败传播的差别。该快照已于2026-09-05获准接入首页列表；接口始终同时给出上游时间和可能延迟限制。

2026-09-06 的详情修复补充了另一个边界：只有行业与概念目录都成功且均无目标代码，
才能回答404“未找到”；任一目录失败时证据不完整，必须返回503。详情成分股同样只有
完整分页才发布，未知价格不补0，避免把“没拿到”伪装成真实零值。

## 备用源失败与业务可用（2026-10-22）

并联备用源不是必须全部健康的依赖。`frontend/lib/backend-health.ts` 将有完整健康指数源的纯指数故障归为 healthy_with_warnings；check 内保留失败事实，UI 折叠诊断。`canCollapseIndexDiagnostics` 另按本次响应检查三指数完整性、缓存、冲突和刷新状态。自己试试：运行 frontend 的 backend-health 与 market-notice 测试，将最后一个 healthy 改为 failed，观察恢复告警。


## 搜索目录与混合故障恢复（2026-10-27）

“有一个可用就先用”需要在数据管道实现，而不只是把红字藏起来。

- `src/data/providers/stock_catalog.py` 把原 AKShare 聚合函数内部已有的沪市主板、深市、科创板、北交所请求独立执行。一个交易所失败时，其他交易所的真实名称/代码继续可搜；完整性随 `StockCatalogSnapshot` 传到消费者。
- `src/data/collector.py::get_stock_catalog()` 只把完整成功目录放入一小时缓存。空结果/部分结果使用独立15秒退避缓存，避免失败被长期固化，也避免连点搜索请求轰炸。旧空成功缓存直接失效。
- 每个交易所最多一个在途任务、总共最多四个；等待预算8秒，超时先返回已取得的部分。等待结束不等于强杀网络线程，晚到结果下一次合并；不可取消的SDK调用仍需运输层超时治理。
- `frontend/lib/backend-health.ts::partitionDiagnostics()` 在“股票目录失败 + 两个指数源失败 + 一个完整指数源成功”时，只计一个未恢复业务问题，两个备用源故障仍在折叠诊断里。价格冲突不能当作可忽略的备用故障。
- `frontend/components/shared/stock-discovery.tsx` 的搜索按钮不只记历史：相同关键词会真正 `refetch()`。新关键词交给 debounce，正在请求时不重复发送。部分目录无匹配只说明这批资料未找到，不证明股票不存在。

**自己试试（5分钟）**：运行 `pytest tests/test_data/test_stock_catalog.py -q`，查看慢沪市与正常深市组合；再运行 `cd frontend && npm test` 的 discovery-retry/backend-status 用例，核对同词重试和混合异常数量。实网恢复例为京泉华002885，测试不依赖该股票的行情涨跌。


## 个股名称和报价也要分层（2026-10-27）

搜索已找到公司，不表示报价接口一定成功；反过来报价失败也不能抹掉公司名称。
`frontend/lib/hooks/use-stock.ts` 的身份读取复用股票目录，严格匹配当前代码，不从旧股票或用户随手输入的名称推断。

`src/data/providers/tencent_display_quote.py` 复用现有日线响应的 `qt`（独立报价快照），而非拿最后一根日线的收盘价伪装实时价格。
`parse_tencent_snapshot()` 同时校验证券类型（个股GP-A/指数ZS）、交易所、代码和数据时间；手转股乘100、成交额直接用人民币元。
`backend/quote_display.py` 用固定线程池与在途表控制实际任务数；9秒等待预算不等于杀死工作线程。同代码同通道正在请求时复用，六个槽位满时在响应预算内等待条件通知，不提前报空，也不无限提交任务。一个有效源就能显示，来源和时间仍可见。

**自己试试（5分钟）**：运行 `pytest tests/test_backend/test_quote_display.py tests/test_data/test_tencent_display_quote.py -q`；慢主源/快备源测试应立即返回备用报价。把qt移除但保留day，必须得到失败而不是历史收盘冒充现价。身份/报价前端回归见 `frontend/tests/stock-identity.test.mts` 与 `stock-page-recovery.test.mts`（本轮页面集成）。


## 空响应也可能是失败（2026-10-27 分时恢复）

**一句话**：HTTP成功只是传输成功，不能让一个“没有有效点”的200把上次成功曲线清空。

`frontend/lib/intraday-recovery.ts::requireIntradayDisplay()` 对不可用信封抛出带诊断的错误；React Query保持同query key的last-good数据，UI同时显示刷新失败与原交易日期。不能将旧数据变成新时间。首次没有last-good时，`useFiveDayDisplay` 复用现有五日分钟接口，只截取真实最后交易日；既不合成分钟，也不提升研究证据等级。两个分钟路径都无数据才默认展示日 K，手选标签不受影响。

**自己试试（5分钟）**：运行 `node --test tests/intraday-recovery*.test.mts`（frontend目录）。真实QueryClient测试先放成功序列，再返回usable=false，检查缓存仍是原对象且状态为error；换证券代码后必须没有前一只股票的缓存。把测试now改为下一天，备用记录必须标历史，不能称当日。


## 同一份数据，不同消费者的门槛（2026-10-27）

展示允许单源、研究却仍要求双源，会造成“看得到但不能分析”的产品矛盾。不是改一行
警告就能修复：`src/data/research_policy.py` 把普通研究策略与严格审计策略分离，
`src/data/quote_runtime.py`、`backend/technical_research.py` 按消费者传入的策略判断。
有效数据的数量门槛可以变，身份/有效价格/时点等数据质量检查不能一起丢掉。
不同更新时间的报价选择最新可比组，而不是一概认定冲突；同刻真实价差仍明确处理。

模型和页面也属于消费者：各研究阶段共用提示；旧生成内容不自动成为当前规则。
`frontend/lib/market-source-policy.ts` 只整理独立旧警告，保留原文和评分，避免“改规则”
被偷换成“把旧看跌改成看涨”。

自己试试（5分钟）：运行 `pytest tests/test_data/test_market_research_policy.py -q`，
分别让仅新浪/东财/腾讯成功，检查完整研究仍可得；再把价格改为0、时点改到未来或
制造同刻价差，确认质量检查没被绕过。前端 `market-source-policy.test.mts` 证明混合
风险句不被误删。全程使用夹具，不产生模型费用。


## 研究缺口：有数据不等于条件满足（2026-11-04）

一句话：先补取得到的资料，再计算现状，不替用户把“还没出现的信号”填成已确认。

`backend/technical_supplement.py` 将日成交股数与前5/20日均量比较（不含当日），短窗口和零分母留空；`src/data/providers/tencent_qfq.py` 只接受明确qfqday，把来源当前复权与raw、官方point-in-time审计分开。
价格前复权因子包含分红，不等于股本变化，所以不能拿它来调整成交量。

自己试试：运行 `pytest tests/test_backend/test_technical_supplement.py -q`，把最新成交量从2000改为500，观察比较从above_both变为below_both。两者均不是数据缺失，也都不能直接推导买入确认。将qfqday改名day，应拒绝而不是假装复权成功。
