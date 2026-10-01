# 板块基本面复用契约 · 2026-10-01

复用既有 GET /api/stocks/{code}/financials、valuation、indicators，不增加供应商或调用LLM。
输入为新浪成分股的六位证券代码，不把新浪板块ID映射为东财BK。

financials 的 data 为 FinancialMetrics 数组，collector按有效ISO报告期倒序后缓存，API再取前10条。
排序不证明最新披露已采齐；报告期必须显示，不能用采集时间替代。空数组不等于公司没有财报。
valuation 的 data 为 ValuationMetrics 或 null；null表示所需财报/报价未取得，不填零。
indicators 的 data 为行业指标定义，空industry/indicators表示未取得，定义不等于实测值。
原有HTTP/错误语义和字段不变；前端独立15秒截止、无自动重试，手动重试。

本轮只提供用户选定成分股的原始多维资料，不把选中样本当作整个行业。
既有零值可能来自缺值填充，统一显示待核验；完整披露日期、字段来源和产业关系仍缺失。
完整行业AI研究暂无服务，market._build_ai_analysis只是行情统计，不作为LLM报告接线。
