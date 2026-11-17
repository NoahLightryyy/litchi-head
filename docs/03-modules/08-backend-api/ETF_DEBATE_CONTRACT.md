# ETF 辩论契约 v1

2026-10-26 冻结；沿用 `/api/debate`，不另造一套只有摘要的 ETF 分析器。
Pydantic 请求、响应与运行时 OpenAPI 均包含标的类型。

## 请求与响应

- `POST /api/debate/run`：`{stock_code: "560780", instrument_type: "etf", question: "..."}`。
  `stock_code` 沿用已有字段名，必须六位数字；`instrument_type` 只接受 `stock | etf`，省略为 stock。
  ETF 名称及交易所从服务端 ETF 目录解析，不接受客户端名称代替身份。
- 成功200：`data = {session_id, status: "completed", stock_code, instrument_type}`，
  `meta.latency_ms` 为总耗时。保持原有同步执行语义，无自动重试付费任务。
- `GET /api/debate/status/{session_id}`：已存在记录包含 session_id、stock_code、instrument_type、
  status、progress、error；未找到仍为 `{data:{status:"not_found",progress:0}}`。
- `GET /api/debate/result/{session_id}`：`{data: DebateResult | null}`；
  DebateResult 新增 instrument_type，其他分析、同侪复核、独立审阅、投票与限制字段不变。
- `GET /api/debate/history?stock_code=560780&instrument_type=etf&limit=50&offset=0`：
  每条包含 instrument_type；先按代码及类型过滤，再分页。省略类型只返回 stock。

## 错误与重试

沿用 `{error:{code,message,detail}}`。输入类型不合法422；未配置模型503
`ANALYSIS_NOT_CONFIGURED`（retryable=false）；目录无此基金404 `ETF_NOT_FOUND`
（retryable=false）；目录不可用、资料全部不可用503 `EVIDENCE_INCOMPLETE`
（capability=etf_research，retryable=true）。资料准备失败会持久化 failed 会话，且不触发模型。
旧客户端以 stock 请求而行情名称识别为ETF时409 `INSTRUMENT_TYPE_MISMATCH`，
提示改用ETF入口，不追加全量股票的目录等待；ETF入口仍通过目录验证真实身份。
未知执行失败沿用500。用户主动重试会创建新会话，不后台反复付费重试。

## 资料与辩论图

`backend/etf_research.py` 同时收集基金场内报价、ETF 原始日线及关键词相关资料，
每类最多等待12秒，目录及准备合计30秒。核对各响应的代码、类型与身份。
任意一类有真实可用数据即可继续；缺项逐条成为 EvidenceLimitation。
三类全部空或失败时停止，避免只拿基金名称付费生成结论。

通过 `InstrumentResearchContext` 进入原 DebateOrchestrator，仍执行分析员、各流派、
同侪复核、独立审阅与聚合。跳过股票公司财务/年报/估值采集；基金结构和主题角色替代
公司基本面角色，ETF 范围说明同步到流派和独立审阅。不得编造持仓、权重、净值、折溢价、
跟踪误差或未计算的技术指标；名称主题和相关报道不视为已核验基金持仓。
资料摘要另用Decimal计算最近5条涨跌额/百分比、前条成交量比（明确不是行情软件量比）、
完整样本覆盖/最低收盘与最大绝对相邻记录变化；无前条或零分母为null，缺口不冒充单日变化。
摘要不推断净资产、分红或折算，有限窗口不外推上市以来，未做生成后事实核验。
行情保留来源与时间；ETF RAW 日线精度及单位见 [日线契约](ETF_KLINE_CONTRACT.md)。

## 隔离与兼容

DebateInput、DebateResult、DebateSessionRecord 新增类型，旧持久记录缺字段视为 stock。
会话类型/代码不可在执行中改变；完成结果类型必须匹配会话。无需改写已有记录及校验和。
前端缓存键、历史列表和结果核对使用类型+代码，旧浏览器历史仅属于股票。
ETF 不写入尚未支持基金语义的股票自动复盘表；ETF 辩论结果本身正常持久化、可重开。
有限资料研究不输出交易执行参数；现有本金核验功能没有因此放开。

## 验证

新增后端接口、资料采集、角色与图回归覆盖：ETF 不走股票采集；五类分析员/流派/同侪/独立
审阅的图路径；至少一类资料成功即可继续；全部缺失及身份冲突在模型前阻断；历史分页前
按类型过滤；旧 stock 默认和错误响应兼容。测试使用受控模型响应，不将其称作实网模型验收。
