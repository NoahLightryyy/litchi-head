# 2026-10-27 分时备用接线与空响应恢复

## 授权与恢复

用户在002885京泉华详情标注“实时数据暂不可用”，要求继续排查反复不可用问题。本轮仅处理分钟展示链路；上轮quote恢复不是分钟恢复。

- 复用 `codex/market-availability` 工作树，起点 `6c0eee6`；session_state inspect为MATCH，核对Git、HANDOVER、最新quote-recovery日志和triage。
- 仅原有frontend/node_modules symlink未跟踪；无其他任务改动。未启动子agent。
- 不调用收费模型、不交易、不修改资金风险默认值、不引入数据商；没有重启后端或打断分析。

## 根因与实测

1. 主分钟链路确有运输故障：旧日志腾讯minute/query返回HTTP501，东财连接失败；本轮还观察到SSL超时以及全源间歇DNS错误。不是“本地结构/时间不合格”这一种原因。
2. 同一腾讯已有day/query五日路径在一次有界实测中返回2026-10-21至10-27的5个交易日、1210个分钟点，无缺失；现有日线展示接口返回160根（2026-03-02至10-26）。旧当日视图没接这条已有备用路径。
3. React Query把HTTP200的usable=false当成新成功数据，覆盖了此前已成功的图。旧“刷新失败保留图”只覆盖网络异常，不覆盖业务空响应。
4. 实网主分钟稍后恢复，返回267点、末时刻2026-10-27 15:30+08:00；随后再次失败时，真实浏览器仍保留267点并显示刷新失败和完整交易日期。未修改或伪造上游时间。

第一次人工API探测误用`/api/evidence/intraday/battlefield`返回404；读现有客户端后改用`/api/v1/evidence/intraday/battlefield`，此404不是产品故障。未循环尝试猜测上游地址。

## 实现

- `intraday-recovery.ts`：业务不可用信封转为携带本次诊断的error，同代码last-good曲线保留；严格核对symbol。
- `useFiveDayDisplay`：复用现有冻结五日接口，备用当日与五日图共享query key。失败/空200不覆盖已有成功记录；15秒预算、30秒正常轮询、关闭自动连续重试。
- 当日初次失败时按北京时间截取五日记录的最后实际交易日。可展示单源点即显示，但不产生不存在的量/额、VWAP或OHLC，也不送入研究证据gate。
- 展示完整日期、最后分钟和来源；较旧交易日注明非今日实时。两条展示路径均不可用时默认日 K，用户手动标签不被覆盖。
- 主分钟20秒客户端请求预算，30秒正常轮询、retry=false。可展开原始诊断，取消笼统的“本地结构与时间校验失败”大框。
- 新代码切换重置选项；涨跌幅仍仅在同股、同北京时间交易日且有有效昨收时计算。
- 图表昨收来源复用已有三源标签，腾讯不再落成泛称“报价源”。
- 后端接口、Pydantic/OpenAPI、研究证据与交易门禁均无变化，无需新增契约冻结。

## 验收

- 前端定向46项通过：分钟回退/日期/未来拒绝、缺口、手选标签、真实QueryClient空200保留、跨股隔离、组件渲染与最新失败诊断、共享查询键、参考价/缩放/quote标签。
- 既有五日后端契约回归6项通过。
- TypeScript、全前端ESLint、ruff全项目、pyright src通过；README public status sync通过；git diff --check通过。
- 真实浏览器002885：当日267点与五日1210点可显示；用户页面恢复到当日。截图 `/tmp/litchi-002885-intraday-recovered.png`、`/tmp/litchi-002885-five-day-recovered.png`。
- 主分钟当时已间歇恢复，未为了截图人为断开数据源；主失败→备用的分支由mock组件/真实QueryClient回归证明，已有备用数据由实网接口与五日页面证明。不能声称生产现场永远可用。
- 临时验收tab已关闭；用户原tab保留。未触发AI生成。

## 五同步与遗留

API消费文档、前端HANDOVER、全局HANDOVER/README、日志索引、学习卡56及债务路由已同步。FW-INTRADAY-RECOVERY-001当轮关闭；ENV-DNS-20261027保持开放，未改本机DNS、代理或网络保护。旧说明在历史日志保留，活跃组件/接口说明已清理。

原文件按每轮原子改写备份于临时目录：
- `/var/folders/hh/fjhkskjj6rb077gbnh5t1f9h0000gn/T/litchi-intraday-backup-m4o__0yf`（主要原始代码）
- `/var/folders/hh/fjhkskjj6rb077gbnh5t1f9h0000gn/T/litchi-intraday-backup-pt2a6mem`（文档）
- `/var/folders/hh/fjhkskjj6rb077gbnh5t1f9h0000gn/T/litchi-intraday-backup-4yy11rhb`（图表来源标签）

## 收尾

仅本地提交，不推送。当前用户问题在显示回退/缓存层完成；后续仅轻量检查或响应新明确缺陷，不重新生成政策解读、不重复跑模型验收。网络本身仍可能使所有源短暂不可用；届时如有同股last-good会保留并显示旧时间，没有历史数据则如实为空。
