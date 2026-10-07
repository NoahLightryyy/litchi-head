# 个股生态位与亮点契约（2026-10-06）

用户要求所有个股页显示公司生态位与亮点，复用已授权的资料驱动 DeepSeek 解读。

- `GET /api/stocks/{code}/company-research`：200 返回最近成功的 `CompanyResearch` 或 null；只读，不采集、不调用模型。
- `POST` 同路径：显式采集主营、最新可取得年度/半年度报告节选并生成；200 返回已持久化结果。所有六位股票共用，不按个股硬编码。普通阅读不会触发付费。
- Pydantic/OpenAPI：`backend/company_research.py`，schema_version=1，purpose=company_context_only；stock_code/company_name、fetched_at、generated_at、model、review_status=ai_unreviewed、sources、gaps、interpretation。
- sources：id/title/url/published_at（未知为null）/excerpt。来源为新浪公司资料与公司公告转载；报告校验公司全称和非未来公告日期。只读取列出的节选，不代表完整审阅/交叉核验/最新实时状态。
- interpretation：niche/upstream/role/downstream，highlights/watchpoints各1–4项，新增competition竞争点1–4项（新生成必须；旧保存结果缺失时默认空数组）。每项text、basis=disclosed|inference、source_ids非空且限输入来源；引用存在检查不等于语义准确率，不输出概率或交易指令。
- SQLite `data/company_research/results.db` 原子覆盖最近成功结果，校验摘要和股票身份。刷新失败保留旧结果，GET展示原生成时间/证据时间。当前不提供版本历史。
- 错误统一 `{error:{code,message,retryable}}`。429 COMPANY_RESEARCH_BUSY；503 COMPANY_EVIDENCE_UNAVAILABLE/COMPANY_RESEARCH_READ_FAILED；504 COMPANY_RESEARCH_TIMEOUT；502 COMPANY_RESEARCH_FAILED。均可重试；422为无效代码。
- 进程内最多2个生成请求、同股互斥、6次/分钟；资料总预算35秒，模型75秒。结构或引用校验失败时在75秒总预算内纠正重试一次，不放宽校验。客户端断线后可GET恢复已完成保存结果；进程中断不续算。
- 无主营资料不调用模型；部分报告失败返回可用资料及缺口。通用产业环节图不声称具体供应关系，研发阶段以相应报告为准。

验收：身份不一致、未知引用、缺失资料、超时、并发、错误保留旧结果、重开SQLite恢复、前端跨股票响应拒绝、出处协议检查。

2026-10-07：competition说明竞争优势、依赖条件和竞争压力；watchpoints突出风险影响与可观察信号。竞争对手、份额和排名仅限输入出处支持，不虚构风险概率或阈值。旧记录提示更新，不把空数组解释成没有竞争。

2026-10-07股票影响扩展：CitedInsight新增可空stock_impact对象，mechanism(1–240字)、
horizon(1–120字)、conditions(1–240字)。旧记录默认null；新的生成结果在highlights、
competition、watchpoints的每项均必须包含该对象；其他产业链字段可为空。影响继承
父项出处，固定视为条件性AI推断，不能把disclosed标签继承成股价事实。
所有错误码及重试/保存策略不变，不新增交易准入或概率输出。
