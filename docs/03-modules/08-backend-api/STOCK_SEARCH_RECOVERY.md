# 股票搜索恢复（2026-10-27）

沿用GET /api/stocks/search?q= 的data(code/name/market)+meta(cached/latency_ms)信封，最多20项；
模型见backend/stock_search_contract.py。空查询返回200空列表。目录可用但不匹配返回200空列表。

全市场目录失败或为空时，完整六位代码可使用已有新浪company_context公司资料解析器恢复身份；
页面股票代码和公司名称/主营业务必须核对通过。已有单股报价只用于匹配公司简称，不能仅凭报价把ETF当股票。
不增加数据源、不触发LLM。恢复失败且目录不可用返回503 STOCK_SEARCH_UNAVAILABLE；不能假装搜索成功但没有股票。
读取失败允许手动重试，前端不循环重试；现有目录搜索不受影响。
