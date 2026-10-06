# 财务展示补充契约（2026-10-06）
GET /api/stocks/{code}/financials 保持 data/meta 包装。data 继承 FinancialMetrics，新增可空 gross_margin_evidence：report_date、source_url（可空）、revenue/cost（元，可空）、reason。
只补缺失毛利率，只匹配同报告期的合并人民币利润表，使用营业成本而非营业总成本。原值不覆盖；缺失、歧义、非正收入或负成本返回 null 与原因；零毛利率有效。单源不声称交叉验证。仅展示层，不改变决策输入。
现有新浪利润表适配器复用；最多两线程、12 秒等待、成功缓存15分钟、失败30秒。失败保留原指标。前端展示报告期、原因、来源与计算依据。
