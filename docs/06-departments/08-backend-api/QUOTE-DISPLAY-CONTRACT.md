# 单股顶部报价展示契约（2026-10-06）

GET /api/stocks/{六位代码}/quote：保持data/meta包裹，不再通过全市场列表筛选。
复用现有EastmoneyQuoteSource，失败后复用SinaQuoteSource；来源身份、正价格、非未来且带时区报价时间验证。
休市报价可显示，真实fetched_at必须保留；这是展示契约，不改变实时AI辩论证据门禁。

data为DisplayQuote或null；open_序列化为open，已有价格/涨跌/成交量等字段保留。
新增source=eastmoney|sina、verification_status=single_source；未双源核验必须明示。
直连未提供的turnover_rate、fund_flow、market_cap为null，前端显示“—”，不能补0。
两源失败返回200/data=null，前端沿用已有重新获取报价状态；逐源失败记录日志。
meta.cached=false，latency_ms为实际耗时。非法代码422；手动重试和现有前端刷新语义不变。
不新建来源、不引入从分时最后点合成完整报价的逻辑、不借此开放交易/辩论门禁。
