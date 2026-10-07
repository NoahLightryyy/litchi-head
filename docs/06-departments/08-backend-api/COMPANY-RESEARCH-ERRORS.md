# 公司解读错误契约（2026-10-07）

POST /api/stocks/{code}/company-research 的成功模型不变。错误仍为 error {code, message, retryable}。

| 状态 | code | 阶段与重试 |
|---|---|---|
| 503 | COMPANY_EVIDENCE_UNAVAILABLE | 主营资料不可用；不调用模型 |
| 502 | COMPANY_RESEARCH_GENERATION_FAILED | 模型调用失败；不作为格式错误重试 |
| 502 | COMPANY_RESEARCH_INVALID_OUTPUT | 结构或引用无效；在总计75秒预算内纠正重试一次后仍失败 |
| 503 | COMPANY_RESEARCH_SAVE_FAILED | 生成通过但保存失败；不覆盖旧记录 |
| 504 | COMPANY_RESEARCH_TIMEOUT | 原有生成总预算耗尽 |
| 429 | COMPANY_RESEARCH_BUSY | 现有并发或频率限制 |

日志包括股票代码、阶段和异常堆栈，校验拒绝另含尝试次数。重试不放宽引用或字段校验，不输出原始异常到用户界面。

错误消息不宣称存在历史结果。前端只有取得有效历史记录才显示历史读取按钮；错误后不再同时显示首次生成引导。旧通用 COMPANY_RESEARCH_FAILED 由上述阶段错误替代；通用客户端仍读取 message，无需猜测新字段。
