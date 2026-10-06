# 资料驱动的产业链 AI 解读契约

2026-10-06 用户批准：复用现有 DeepSeek，根据核验资料生成解释和结构图；公司关系必须有来源。

`POST /api/market/sector/{BKdddd}/chain-analysis`，无请求体；GET不触发生成。
后端只读已核验本地目录，缺目录404且不调用模型。图沿用现有ChainEvidenceMap，模型仅解释既有节点，
不能新增图节点、关系或来源。BK1106增加2020年药品注册管理办法支持的5环节流程，范围不含完整商业供应链。

成功200，直接返回（无data包裹）：

- sector_code：请求BK代码；evidence_revision：核验目录规范JSON的SHA256。
- interpretation：summary字符串；stages数组，每项node_id、explanation、source_ids。
- stages恰好覆盖全部核验节点，不能重复；source_ids必须来自该节点既有引用。
- generated_at：UTC ISO时间；model：现有DEFAULT_MODEL；cached：布尔。
- review_status固定ai_unreviewed；citation_coverage固定1.0，**仅表示引用覆盖率，不是事实正确率或置信概率**。

错误使用error对象：code、message、retryable。404 CHAIN_EVIDENCE_MISSING、503 CHAIN_EVIDENCE_INVALID不可重试；
429 CHAIN_AI_BUSY、502 CHAIN_AI_FAILED、504 CHAIN_AI_TIMEOUT可由用户点击重试，不自动循环。
默认限流6/minute（受项目全局限流开关控制），全局最多2个生成、同资料只允许一个正在生成。
模型时间预算45秒；只调用src/utils/llm.py，固定DeepSeek、现有默认非思考模型，不切换或配置凭证。
进程缓存1小时、最多32条，目录或模型变更失效。模型输出校验失败不缓存；不承诺重启保留。

前端按钮按需生成；loading/error/offline提示与原资料图独立。刷新报价不生成AI。
解读以纯文本展示并显式标记“AI解读·未经人工复核”；每环节可查看既有依据。
结构图由已核验节点/关系绘制，不能将AI自由文本解析成已核验供应商图。
