# 个股生态位与亮点契约（2026-10-06）

用户要求所有个股页显示公司生态位与亮点，复用已授权的资料驱动 DeepSeek 解读。

- `GET /api/stocks/{code}/company-research`：200 返回最近成功的 `CompanyResearch` 或 null；只读，不采集、不调用模型。
- `POST` 同路径：显式采集主营、最新可取得年度/半年度报告节选并生成；200 返回已持久化结果。所有六位股票共用，不按个股硬编码。普通阅读不会触发付费。
- Pydantic/OpenAPI：`backend/company_research.py`，schema_version=1，purpose=company_context_only；stock_code/company_name、fetched_at、generated_at、model、review_status=ai_unreviewed、sources、gaps、interpretation。
- sources：id/title/url/published_at（未知为null）/excerpt。来源为新浪公司资料与公司公告转载；报告校验公司全称和非未来公告日期。只读取列出的节选，不代表完整审阅/交叉核验/最新实时状态。
- interpretation：niche/upstream/role/downstream，highlights/watchpoints各1–4项。每项text、basis=disclosed|inference、source_ids非空且限输入来源；引用存在检查不等于语义准确率，不输出概率或交易指令。
- SQLite `data/company_research/results.db` 原子覆盖最近成功结果，校验摘要和股票身份。刷新失败保留旧结果，GET展示原生成时间/证据时间。当前不提供版本历史。
- 错误统一 `{error:{code,message,retryable}}`。429 COMPANY_RESEARCH_BUSY；503 COMPANY_EVIDENCE_UNAVAILABLE/COMPANY_RESEARCH_READ_FAILED；504 COMPANY_RESEARCH_TIMEOUT；502 COMPANY_RESEARCH_FAILED。均可重试；422为无效代码。
- 进程内最多2个生成请求、同股互斥、6次/分钟；资料总预算35秒，模型75秒。不自动重试模型。客户端断线后可GET恢复已完成保存结果；进程中断不续算。
- 无主营资料不调用模型；部分报告失败返回可用资料及缺口。通用产业环节图不声称具体供应关系，研发阶段以相应报告为准。

验收：身份不一致、未知引用、缺失资料、超时、并发、错误保留旧结果、重开SQLite恢复、前端跨股票响应拒绝、出处协议检查。
