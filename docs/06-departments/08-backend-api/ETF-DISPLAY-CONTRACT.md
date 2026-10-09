# ETF搜索及独立行情展示契约 v1

2026-10-09 用户批准方案并要求执行。Pydantic定义：backend/etf_contract.py。

- GET /api/discovery/search?q=：原SearchHit增kind=etf；字段仍code/name/kind，
  ETF类别查询不要求源简称含ETF；仍返回total、data（最多100项）、failed_sources。
  目录失败追加“ETF目录”；股票目录失败不丢ETF结果。
- GET /api/etfs/{code}：200原始EtfDetail对象（不包data），schema_version=1。
  identity包含code/symbol/exchange/name/instrument_type；仅经新浪ETF分类目录确认的身份。
  quote含价格、前收、价格差、百分比、可空OHLC、原始简称、完整时区报价时间。
  status=ready表示此来源返回有效价格，仍单源未交叉验证；行情失败status=partial/quote=null。
  catalog_fetched_at仅目录采集时点，fetched_at仅响应采集时点，都不能替代quoted_at。
  source=sina，source_url为该ETF新浪行情页，limitations给出单源、报价故障等边界。
- 404 ETF_NOT_FOUND：目录成功但没有代码，禁止按前缀自动当ETF。
- 503 ETF_CATALOG_UNAVAILABLE：目录未完整取得或校验失败；retryable=true。
- 错误JSON：error.code/message/detail.retryable；格式非法代码422。
- GET可重试，不触发分析。行情返回旧日期时如实显示；无完整日期/未来时间/错symbol/非正价格
  不展示报价。源简称允许与目录简称不同，二者分字段，身份只按精确symbol。

生产范围：沪深场内ETF，目录来自新浪etf_hq_fund。逐页100条，通过数量前后核对、严格
身份去重、排序和结束页验证完整性；仅完整快照进入缓存。缓存最长1小时，过期失败不冒充新目录。
ETF独立/etf/[code]页，不调用个股财务和辩论；首批不提供净值/溢价、费率、持仓穿透。
错误文案：目录“ETF目录暂时不可用，请稍后重试”；未知“未在当前ETF目录中找到此代码”；
行情“ETF行情暂时不可用，可稍后刷新；基金身份仍可查看”。用户批准方案后冻结此显示边界。
