# 辩论前置检查修复（2026-10-01）

POST `/api/debate/run` 保留成功响应、会话和结果契约。
请求 `stock_code` 限定六位数字，非法代码422，进入数据采集前拒绝。

- 模型配置缺失/不支持：503，`error.code=ANALYSIS_NOT_CONFIGURED`，
  `error.detail={capability: analysis_service, retryable: false}`。不创建会话，
  不采集数据、不调用模型；需要恢复服务器DeepSeek配置，重复点击无效。
- 股票名称查询超时/不可用：沿用503 `EVIDENCE_INCOMPLETE`、
  `detail.capability=stock_identity`、`missing_fields=[stock_name]`、
  `retry_after_seconds=300`、`Retry-After: 300`，不再落入通用500。
- 意外引擎异常仍500，证据完整性错误仍按原契约503，不绕过证据门禁。

名称通过已有新浪、东方财富单股适配器顺序查询，优先新浪。
只投影已校验股票代码的名称，不把该次单源报价充作辩论证据。
成功名称缓存300秒、最多256项；最多4个进行中的同步查询，饱和立即拒绝，
适配器已有5秒HTTP超时，路由总等待保持15秒；取消等待不等于终止工作线程。
新闻聚合复用同一名称解析实现，股票目录搜索接口不变。

OpenAPI 503响应为 `DebateUnavailableResponse`，错误码枚举冻结为上述两种。
验收：34项后端专项通过；法国网络300199单股名称约1.9秒返回。
用户新凭据已安全保存；用户批准临时V4 Pro非思考，文本与结构化生成已实测成功。

## 现有结果字段确认（2026-10-01）

`GET /api/debate/result/{session_id}` 的 data 为 `DebateResult`，保持已有字段：
- evidence_limitations: 数组，元素 status=limited、capability:string、
  missing_upstream_ids:string[]、missing_independent_upstreams:number、
  source_statuses:Record<string,string>、collected_at:ISO datetime。
- review_report: IndependentReview 或 null；null 不能显示为已完成独立评审。
- analyses[].success 为实际成功标记，不能把失败条目当作有效分析。
证据有限时仍执行既有带限制研究，禁止进入交易链；前端必须消费限制字段。

复盘价格采集在线程数2的独立池中运行，等待沿用DATA_TIMEOUT=15秒；超时保留
price_at_debate=null并写日志，不阻断已完成结果。分析辅助市场情绪仅读取现有
all_quotes有效缓存，失效/空缓存为None，简报沿用“暂无数据”，不查询整个市场。
成功run接口仍同步返回completed。Next代理等待600秒匹配多轮研究，后台任务化
与断线重连属于后续改造，不声称本次已经实现。

最终真实浏览器验收：300199 / deb_4dbc931dd41d，run与result均200，研究191.205秒；
5份分析师报告、5位策略师成功、5份交叉评审和独立评审返回。evidence_limitations
明确包含realtime_quote/news；trade_recommendation=null，前端显示有限信息研究。
复盘报价超时仍保存记录，price_at_debate=null。独立3002/8002通过，未集成3001。

## 会话身份一致性修复（2026-10-06）

`POST /run` 创建的 `deb_*` ID 必须显式传入 `DebateInput.session_id`，贯穿编排、结果与复盘。
`GET /status/{id}` 与 `GET /result/{id}` 返回的 session_id 必须等于启动返回值；前端继续拒绝不匹配结果。
实测 920344：启动 ID deb_c14996d54447，而原结果 ID 为 b9d08532-ea5c-4296-9d32-f86a2bce21aa。
两请求均 200、5份大师分析已生成，但前端按既有防串线规则隐藏。根因是路由遗漏输入 ID，触发模型默认 UUID。
修复只传递同一 ID，不调整数据门禁、置信度或错误文案。路由测试以前的 mock 未模拟 session_id，现增加全链一致断言。

## 休市研究契约（2026-10-06，用户确认）

- 新增可选 `evidence_limitations[].research_note: string | null`：后端生成的研究范围说明，同时写入模型简报；旧结果缺省 null。
- 数据层 `SourceResult` 可携带 `coverage_start_at` / `coverage_end_at`，表示缓存实际连续观察范围；不把缓存数据条数当作完整覆盖证明。
- 仅研究层采用官方年度交易日历核验的最近已结束交易日、15:00以后的报价。拒绝未来时间、过旧交易日、午休/竞价期间旧报价和未知日历覆盖。多源价格相差超过1个最小价位时不使用，收盘时间戳秒差不作为冲突。
- 保留原实时证据信封及其 `complete=false`，单源明确标注，休市数据不进入交易决策。实时 API 和交易门禁不放宽。
- 新浪仍按原有源分页补采。未覆盖近3天时，STALE结果保留实际缓存范围及匹配条目，研究仅使用该范围内、同股票的新闻。匹配0条只表示已覆盖范围内未匹配，不能声称近3天无新闻。
- `_evidence_limitation` 补传已有 `error_codes` 字段，避免后续只剩笼统 stale/failed。
- 前端优先展示 `research_note`，其余缺失能力保留旧通用说明；有具体说明时仍明确有限信息研究、未进入交易决策。

## 完整研究历史与断线恢复（2026-10-06 用户批准）

- 路由正式使用 `data/debate/sessions.db` 的 SQLite WAL 会话存储，结果、证据限制、时间戳与校验和一同保存。保存失败返回服务错误，不能声称成功；完成的结果不可覆盖。
- `GET /api/debate/history?stock_code=六位代码&limit=50&offset=0`：`data` 按 created_at 降序返回 session_id、stock_code、status（queued/running/completed/failed）、created_at、updated_at、error；limit 1–100。
- 原 status/result 路径从持久库读取，状态新增可空 error；result 仍为完整 DebateResult 或 null。身份必须同时匹配会话与股票。
- 创建分析时先保存 running，再执行原同步流程；断线不会删除持久记录，可通过个股历史查询找到进行中/已完成的分析。前端独立轮询历史恢复，无需重复提交。
- 单进程启动把上次未完成会话标为 failed，error 明示服务重启中断；不自动再次调用模型。此交付不代表 durable queue / 跨进程续算 / 全局并发预算已实现。
- 个股页默认展示最新完整结果，可选择更早记录；刷新保留历史可见性。新分析期间旧结果须明确标为历史，不能冒充本次输出。失败或超时后可手动选择已完成历史。
- 旧复盘摘要保留在研究与复盘；只有现存可核验完整结果迁入本库，不从摘要伪造完整结果。
