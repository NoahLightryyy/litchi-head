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
