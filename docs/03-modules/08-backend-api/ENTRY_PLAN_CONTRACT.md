# 条件买入与分批计划 API · v1

2026-10-27 冻结。供股票与 ETF 已完成辩论使用，不改旧交易员默认值、不提交订单。

## 路由与读取语义

`GET /api/debate/{session_id}/entry-plan` 返回已保存的 `EntryPlanResult` 或 `null`；读取绝不调用 LLM。

`POST /api/debate/{session_id}/entry-plan` 请求仅 `{ "refresh": false }`。默认复用已保存成功结果；显式 `true` 重新生成，失败保留原结果。同一会话不可并发生成，全服务最多两次生成。仅接受已完成且身份一致的辩论。服务补采该股票或 ETF 的行情与日线，单项失败保留其他资料。

成功直接返回对象（无 data 包装）：`schema_version:1, session_id, source_session_id, source_research_generated_at:ISO时间, stock_code, instrument_type:stock|etf, stock_name, generated_at:ISO时间, model, evidence, gaps, cached, purpose:conditional_research_plan, status_basis:ai_review_of_dated_evidence, plans`。两个 session_id 必须相等；source_research_generated_at 为原辩论最近流派生成时点（旧记录无该字段时使用会话完成时间），generated_at 是本计划生成时间，行情时间在 evidence.data_time 中，不得混用。

## 精确字段

权威模型：`backend/entry_plan.py`。可用 `EntryPlanResult.model_json_schema()` 导出完整 JSON Schema。

- `evidence[]`：`id, kind:analysis|quote|daily, title, data_time:string, content:string`。资料由服务端建立，模型不能新增来源。analysis 是既有 AI 研究，不是独立核实的事实；quote/daily 保留来源与原数据日期。
- `plans`：恰好短中长各一项，`horizon:short|medium|long`。
- 每项 `status:consider|waiting|insufficient`、`summary:string`。
- `conditions[1..6]`：`condition:string, status:met|unmet|unknown, explanation:string, evidence_ids:string[]`。状态是 AI 对所示时间资料的核对，不代表实时监控。无验证依据必须 unknown。
- `entry_low:number|null, entry_high:number|null, stop_loss:number|null`：三项同时有值或同时 null。有值须为有限正数且 `stop_loss < entry_low <= entry_high`；`price_basis:string` 解释计算/研究依据，`price_evidence_ids:string[]` 至少引用实际 quote/daily。候选价是条件性建议，不是行情事实或保证成交价。禁止固定8%止损及无依据阈值。
- `invalidation[1..5]:string[]`；`batches[1..4]` 每项 `{budget_pct:number, trigger:string}`，比例大于0、最多两位小数且总和100%，指本计划预算的分配，不是账户总资产仓位。
- `position_note:string`；`limitations[1..6]:string[]`。不提供账户仓位默认比例。资金/账户数据不发送模型；前端按用户填写预算和允许损失测算上限。position_note由服务端规范，忽略模型对此字段的资金保证，固定说明：“资金规模由用户填写的可用现金、投入上限和新增风险预算在本地试算；仅按计划价格估算，实际亏损可能超过估算，未计入费用、滑点与已有持仓风险。”生成保存和读取旧缓存投影都使用此说明；读投影不改写原存储。
- `consider` 只有全部 conditions 为 met 且候选价格有效时才允许；看跌结果仍可提供将来转强的 waiting 条件计划，不把看跌成立条件冒充买入信号。

所有对象禁止额外字段，所有数值禁止 NaN/Infinity。引用必须来自当次实际输入证据；不从其他标的补用。

## 本次资料优先与历史语义

模型输入先列本次quote/daily及程序计算的MA、最近20根高低，再列旧AI观点摘录。MA四位小数；计算使用补采完整序列，提示中只列最近20根日线，完整来源仍随结果保存。单源行情可供条件研究，双源一致不是该功能前置门槛；本次已有MA时，不得照抄旧辩论“指标全部缺失”的描述。日线价格锚点可用于未来回踩/突破确认场景，候选价需要解释入场和撤销关系；资料确实不足仍允许null，不为填字段编造价格。优先设计2至3个不同条件阶段，避免100%单批加“暂不买”替代分批研究。

旧AI财务、新闻、公告描述没有本次重新核验，只能作为历史主张。任何含analysis引用的条件（包括混合新quote与旧AI）由服务端明确降为unknown，说明“包含历史AI引用，本次未重新核验相关事实”；有此项则不能consider。新报价不能把旧AI净资产/盈利主张升级为当前已核PB/PE；summary和price_basis也必须保留假设性质。生成和缓存读取都适用状态校正，读取仅投影不改保存历史。同日量口径明显冲突单列，不声称跨源放量已确认，也不抹去可用价格与MA。市场事实与历史分析生成时点分别保留，状态仅对应显示的资料日期。

每周期选择一个连贯价格场景，conditions是同时必要的条件集合，不把“回踩”和“突破”备选方案混装为全部必选条件；候选价、撤销价、分批trigger须对应同一场景。其他备选只能单独注明需另行研究。

## 错误与持久化

统一 `{error:{code,message,retryable}}`，中文 message 稳定。404 `ENTRY_PLAN_NOT_FOUND`；409 `ENTRY_PLAN_SESSION_NOT_READY`；429 `ENTRY_PLAN_BUSY`；504 `ENTRY_PLAN_TIMEOUT`；502 `ENTRY_PLAN_INVALID_OUTPUT` / `ENTRY_PLAN_FAILED`；503 `ENTRY_PLAN_READ_FAILED` / `ENTRY_PLAN_SAVE_FAILED` / `ENTRY_PLAN_NOT_CONFIGURED`。请求结构不合法返回 FastAPI 422，不启动推理。

SQLite 按 session 原子保存最后成功结果，包含证券身份、模型、证据与生成时间，校验哈希与引用。历史方向研究不被覆盖。单次生成总超时120秒（包含补采），每路补采16秒；应用只调用一次 `llm_service.invoke_structured`，不额外重跑辩论或重试生成，底层沿用统一LLM层的供应商重试策略；失败后用户可显式重试。股票 DisplayQuote.fetched_at 沿用东财f86/新浪日期时间字段的报价时点，ETF取quoted_at，日线取最后交易日期。
