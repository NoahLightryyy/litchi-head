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
用户新凭据已安全保存，真实LLM闭环仍待旧模型迁移确认与生成验收。
