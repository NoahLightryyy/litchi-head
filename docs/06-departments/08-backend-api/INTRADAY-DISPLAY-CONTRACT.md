# 分时展示契约补齐（2026-09-09）

POST /api/v1/evidence/intraday/battlefield，保留既有字段及错误语义，新增usable、verification_status、canonical_source_id、available_source_ids、failed_source_ids、as_of、price_points及诊断source_name，对齐现有前端强校验。

complete仍表示原双源证据策略达标。单个SUCCESS_DATA来源可提供原始价格点，标single_source，complete=false，bars/snapshot不伪造；stale/conflicted只保留诊断，不能成为曲线。失败重试不改变来源策略。

实测300913旧后端HTTP200缺字段，前端正确拒绝。腾讯267检查点存在而旧响应bars为空；本次补充展示信封，不降低研究完整性判定。K线默认日期传空串问题同期修复，但东方财富仍发生ProxyError，不能宣称历史行情恢复。

验证：后端API、数据提供者、分时引擎/证据123项测试通过。前端消费须在此提交之后做真实页面验收。
