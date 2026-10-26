# 政策与相关资料解读契约 v1

## 范围

把现有相关资料按事件归并，解释报道说了什么、可能如何影响产业与当前标的，以及还应观察什么。它是未人工复核的 AI 解读，不是正式证据包、实时行情、订单结论或买卖建议；不新增资料源，不要求多个来源同时成功。

## API

`GET /api/research/related/interpretation` 返回 `null | RelatedInterpretationResult`，仅读取上次成功结果，不检索、不调用模型。

`POST /api/research/related/interpretation` 显式生成，返回 `RelatedInterpretationResult`。请求正文仅包含布尔字段 `refresh`（默认 false，正文可省略）：已有同键成功结果时直接复用，不重新检索或调用模型；首次生成、或刷新按钮传 `refresh: true` 时服务端重新检索并生成。客户端不能提交文章或模型提示词。只有服务器调用既有 `related_research` 取得的快照可进入模型。

两者查询参数相同：`kind=stock|etf|sector`、`code`、可选 `name`（最多 120 字）、可选 `q`（最多 80 字，前后空白忽略）。股票/ETF 代码六位；板块为 `BK` 加四位数字或 `sina:` 加字母数字下划线。`q` 沿用现有关键词规则。持久化键为 `(kind, code, q)`，不以显示名称区分。无记录返回 `null`。

POST 全过程最多 120 秒，最多两个并发，同键重复请求返回 429，不再发起生成。服务只执行一次结构化模型调用，不额外重试。调用经过 `src/utils/llm.py`，采用 `DEFAULT_MODEL`，不启用思考模式。刷新失败保留旧成功结果，GET 不自动补发任务。

本功能显式指定 `output_method="json_mode"`，提示版本为 `related-materials-v2-json`。统一调用层发送 `response_format={"type":"json_object"}` 并在系统消息注入完整 Pydantic JSON Schema；收到消息后先记录用量，再用 `model_validate_json` 校验完整 JSON。空响应、普通文本、缺字段、非法 JSON 或 `finish_reason=length` 均失败，不补括号、不修复截断、不因解析失败自动再生成。网络异常仍使用统一层已有的有限重试。本功能以外的调用继续默认 `function_calling`，没有全局切换。

选择 JSON 模式的背景：2026-10-26 实测工具模式两次 HTTP 200，返回元数据为 `finish_reason=tool_calls`，但解析结果为 `parsed=None` 且 `parsing_error=None`；另一 `InvestmentAnalysis` 调用也出现相同症状。未保存原始返回，不能断言供应商缺了哪个字段。这里采用显式格式路径回避不可用工具输出，保留全部来源和内容校验；排查步骤见 [结构化输出急救](../../01-guides/triage/llm-structured-output.md)。

| HTTP | 错误码 | 含义 |
|---|---|---|
| 422 | `RELATED_INTERPRETATION_INVALID_REQUEST` | 参数、关键词或请求正文不合要求；不可重试原请求 |
| 429 | `RELATED_INTERPRETATION_BUSY` | 同键或全局生成繁忙；可稍后重试 |
| 503 | `RELATED_INTERPRETATION_SOURCE_UNAVAILABLE` | 没有可用材料或检索失败；未调用模型 |
| 503 | `RELATED_INTERPRETATION_READ_FAILED` / `RELATED_INTERPRETATION_SAVE_FAILED` | 保存结果读取或持久化失败 |
| 502 | `RELATED_INTERPRETATION_GENERATION_FAILED` / `RELATED_INTERPRETATION_INVALID_OUTPUT` | 模型调用失败或结构/引用未通过校验 |
| 504 | `RELATED_INTERPRETATION_TIMEOUT` | 本次请求超时；旧结果保留 |

服务错误体为 `{ "error": { "code": "...", "message": "...", "retryable": true } }`。FastAPI 对缺失参数、枚举、长度、正文结构及禁止的额外字段的基础校验沿用 422 `detail`；前端需同时处理这两种错误体。

## 返回结构

Pydantic 事实源：`backend/related_interpretation_contract.py`。

- 顶层包含 `schema_version=1`、`subject_kind/id/name`、`query`、`generated_at`、`model`、`prompt_version`、`review_status=ai_unreviewed`、`purpose=related_material_context_only`。
- `status` 为 `interpreted`（至少一组事件）或 `no_relevant_events`（全部材料不适合展开解读）。
- `snapshot` 完整保存既有 `RelatedResearchResult`，包括来源链接、发布时间、节选、匹配理由及检索限制；`snapshot_sha256` 为其标准 JSON 的 SHA-256。生成时间不能代替报道时间。
- `analysis.overview` 为通俗综合解读；`events` 为 0–6 组；`excluded_sources` 记录排除来源及原因；`limitations` 记录这次解读的实际缺口。

每组事件：

| 字段 | 内容 |
|---|---|
| `title`, `source_ids` | 事件标题及归属材料 ID |
| `summary` | `{text, basis: reported, quotes:[{source_id, field:title|excerpt, quote}]}`；概况只能复述输入明确记载的内容 |
| `impact_direction` | `positive|negative|mixed|unclear`，属于条件性推断，不能当已发生的收益 |
| `impact_path` | 产业传导路径 |
| `affected_scope` | 可能涉及行业、地区、产业环节，不能凭名称推断实际订单或 ETF 持仓 |
| `duration` | 影响持续期及成立条件；原文的明确政策目标期在 `summary` 引用，不等于收益持续期 |
| `market_reaction` | 情绪、风险偏好、预期变化可能的速度；没有行情证据不能断言实际涨跌、已定价或未定价 |
| `business_realization` | 订单、建设、交付、收入、利润等兑现节奏及中间条件 |
| `subject_relation` | 当前股票/ETF/板块与事件的联系及缺口；主题命中不等于直接受益 |
| `watchpoints` | 1–4 个后续可核查线索，不编造阈值、具体订单或概率 |

六个推断维度统一为 `{text, basis: inference}`。不能判断时直接说明资料不足，不强行给精确持续年数。事件归并属于模型判断；同一事件的转载不算独立验证。

## 引用与完整性

所有输入资料必须且只能归属一个事件或一条排除记录；事件内来源 ID 不得重复。每条 `summary.quotes` 的 ID 必须属于本事件，`quote` 必须是对应 `title` 或 `excerpt` 的连续非空子串。此校验证明引用存在，不代表已经独立核验概况或推断的语义。

新生成结果先整体校验全部来源 ID、事件归属和完整分配。通过后，若模型把同来源引用文字复制错，服务端不显示这段模型文字，改为从该来源对应字段直接截取最多 300 字的真实连续片段；字段为空或不足两字时采用同来源真实标题。正确引用原样保留。处理会记录标的及恢复条数，并在 `analysis.limitations` 标明部分引用采用服务端原始片段。概况文字与 `reported` 状态不因此改写或升级，片段不等于摘要获得语义核验。未知来源、空 ID、跨事件引用、遗漏或重复归属仍拒绝；存储、GET 和历史复用只做严格校验，不自动修补旧缓存中的错误引用。

`news_archive` 的 `excerpt` 是接口保留的报道节选，可能只有标题，不代表全文。`policy_archive` 的 `excerpt` 是已有档案摘要，必须称“档案摘要”，不能冒充政策原文；其标题仍可作为标题引用。输入没有正文时只按标题作有限概况，不补写未提供条款。任何来源文本都属于资料，不是模型指令。

相同事件的重复报道应合并，券商测算必须保留测算者，不变成政府预算。历史计划必须保留原时间窗口；窗口结束不能推断执行结果或仍在实施。弱相关材料可直接排除，不为凑事件解释利好。所有资料为空时不调用模型；单条、单源、标题材料不因数量而被阻塞。

## 保存与后续消费

SQLite 保存完整结果及整体 SHA-256，读取时校验整体哈希、快照哈希、身份和引用归属。成功才替换同键旧结果。新增模块提供同步 `get_saved(kind, code, query='') -> RelatedInterpretationResult | None` 及 `format_saved_interpretation(kind, code, query='') -> str`，后者内部同键读取，无记录返回空字符串，损坏则抛异常由消费者记录；两者均无网络或模型调用。默认辩论只读取 `q=''`，不自动付费生成。格式化材料保留快照 ID、生成时间、来源日期、URL 和历史未复核标记，当前原始资料优先，不能把 AI 推断转写为事实证据。

## 2026-10-27 综合解读扩展（向后兼容）

保留schema_version=1与现有端点、错误和只读缓存语义。`analysis.synthesis`新增为可空字段；旧记录缺字段按null处理，不自动重新生成。
新模型输出使用`RelatedInterpretationGeneration`：最多3个主线事件，有事件必须有一份综合解读，无相关事件则synthesis=null。
综合解读由what_happened（240字以内）和price_impact、industry_impact、duration、market_reaction、business_realization五项条件性推断（每项180字以内，basis=inference），以及最多3条watchpoints和source_ids组成。
它综合所有保留事件，source_ids必须恰好覆盖各事件来源，不得引用排除材料；资料事实仍在事件原句中追溯。
产业影响包含上中下游/需求成本竞争及影响边界；持续条件与市场情绪、订单收入利润的兑现时间分开。
默认页面展示一份综合结论，事件依据折叠。旧结果显示兼容摘要并保持旧时间，不把缺字段当失败或触发付费。
复制与后续股票/ETF辩论都携带同一综合解读、来源和日期；AI推断不升级为事实。
