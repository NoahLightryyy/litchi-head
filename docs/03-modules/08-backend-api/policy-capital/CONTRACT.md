# 政策与本金证据契约 v1

状态：v1证据读取、研究任务与单笔限价买入测算契约冻结。实现源 `backend/policy_capital_contract.py`，本目录 `openapi.json` 为设计契约。四个v1端点已注册到本地backend.main；实际账户证明适配与实网模型质量仍待验收。

## 冻结范围

`GET /api/research/evidence/{package_id}` 返回 EvidencePackage。ID是不透明的版本标识；同一ID内容不可被覆盖，更新证据生成新ID。来源按canonical_document_id去重，转载不是独立证据。claim引用只能指向包内证据。结构校验不代表引用语义已经核验。

200包括partial和verified_scope：partial必须有缺口；verified_scope仅表示声明范围内证据齐备，不表示投资结论可靠或收益保证。历史持仓保留as_of、published_date和coverage；净值权重不归一化，缺失持仓不得当0。日期不互填；未明确生效或存在冲突时effective_date为null。retrieved_at必须有时区，snapshot_sha256允许null以如实体现未归档。

404 PACKAGE_NOT_FOUND：不自动重试；422 VALIDATION_ERROR：修正输入再提交；503 SOURCE_UNAVAILABLE：可按retry_after_seconds重试，未提供间隔则人工重试，不无限轮询。错误体统一code/message/retryable/retry_after_seconds；FastAPI默认422必须在实现阶段替换为该错误体并做HTTP消费者测试。

执行器必须使用Decimal或分整数、明确价格时点、规则版本、买卖方向、订单类型与最低/递增单位；板块不返回可交易数量。缺用户输入或规则时返回缺口，不能给精确数量。模型不能直接计算可买数量或猜客户费率。

## 验证

契约单测验证悬空引用、无证据事实、历史持仓不归一化和错误重试约束。证据模型未先RED；任务和测算先RED后GREEN，流程偏差保留。HTTP消费者和浏览器缺项/预算/返回恢复测试已完成，见本文件S4/S5节。

## v1 冻结补充：研究任务与单笔买入测算

完整组合适配/压力测试/卖出仍在后续范围。研究任务与单笔测算已加入同一Pydantic/OpenAPI，并已挂载本地后端。

- POST /api/research/jobs：202，显式预算max_cost_cny（人民币估算上限）及idempotency_key；同key同规范化请求返回原任务，同key异请求409 IDEMPOTENCY_CONFLICT，不扣第二次费用。任务必须先落盘再调用模型。
- GET /api/research/jobs/{job_id}：200 queued/running/succeeded/failed。succeeded必须有result且无error；failed必须有error且无result。结果携带标的、证据包版本、模型、提示版本、生成时间和估算成本。服务端验证每项引用存在于指定包，目标身份一致。
- queued→running→succeeded/failed；重启后无法恢复的running写failed/INTERRUPTED，禁止长期假运行。失败不会自动重新扣费；用户显式新key重试。BUDGET_EXCEEDED不可原预算直接重试；SOURCE_UNAVAILABLE/MODEL_FAILED/INTERRUPTED允许用户重试。成本为估算，不冒充账单。取消不在v1。
- POST /api/research/execution-preview：200 ready/blocked。v1仅沪深股票/ETF二级市场单笔限价买入预算计算，不覆盖卖出、一级申赎或组合适配。所有可缺输入必须显式null；缺权限、现金、预算、价格时间、有效交易规则或完整客户费用时blocked，数量/费用/余额全部null且有gaps。金额JSON使用十进制字符串；rate使用0—1比例，持仓nav_weight_pct使用0—100百分数，禁止混淆。
- ready之前校验规则与来源、标的/交易方式匹配、日期有效、价格步长及价格时效；不得只信任客户端上传规则/费用。买入金额不超过min(可用现金,用户预算)，数量按min_quantity + n×quantity_step且不超过max_quantity，佣金=max(成交额×佣金率,最低佣金)，附加费用只包含尚未计入佣金的全部适用客户税费，最终按人民币分向上取整；无法确认完整费用时阻断。数量不足最低值也blocked。剩余资金以可用现金减含费成本计算。
- 价格时效、费用证明与账户授权核验需由PC-05/06实现并配置，未知时阻断；不引入默认风险比例。ready只表示该单笔预算计算可完成，不能宣称适合用户或可以买入。

新增任务与缺项阻断用例先出现ImportError（RED），实现后6项测试通过。证据模型首批4项未先RED的流程偏差保留记录。

契约冻结提交：`5a4ec25`。重新导出：仓库根目录执行 `PYTHONPATH=. .venv/bin/python scripts/export_policy_capital_contract.py`。该脚本仅输出设计OpenAPI，不启动服务。

## S4/S5 实现与接入（2026-10-18）

v1四个端点已注册到backend.main。政策服务启动/停止显式恢复/终结SQLite任务，当前只支持单后端worker。已归档5份官方材料，manifest记录原始字节SHA-256与真实抓取时间；GET证据每次校验归档。版本包为v1-sector-BK0917、v1-stock-688012、v1-etf-512480，其他标的404，不借用不相关结论。

研究任务预算按最高峰值价格与最多18次底层尝试保守预留；不足时模型零调用。输出estimated_cost_cny目前为保守预留上限（结果同时说明），不等于实耗。supported/contradicted事实必须与已核验事实的文本、评估、引用集合一致；新增推断必须引用包内证据并保留缺口。此结构保护不等于模型质量通过实网验证。

本金计算器已经实现、可信服务端上下文测试可返回ready。生产没有账户/完整客户费用核验适配器，默认blocked；前端输入不构成证明。已归档交易规则发布页也不能直接冒充全部委托条款已核验。计算规则按上海日期生效，金额Decimal，费用按分向上取整，精度异常阻断。

前端四类详情页通过ResearchContext共用PolicyCapitalPanel；ETF研究不再依赖行情成功，东方财富板块行情错误时仍可读取独立证据。任务恢复未完成或状态未知时禁止新建付费任务；POST结果未知复用原幂等键。完整持仓/实际费用/账户核验/组合适配与卖出仍未实现。
