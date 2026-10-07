# 三周期条件研究契约（2026-10-06）
用户确认每次同时研究 short（1–5交易日）、medium（1–3个月）、long（1–3年），不合成跨周期方向。
AgentAnalysis 新增 horizons（默认空数组兼容历史），每项：horizon；status supported/insufficient；direction Bullish/Bearish/Neutral/null；thesis；assumptions[]；invalidation[]；review_on ISO日期；review_trigger；evidence[]；limitations。Pydantic HorizonOpinion 冻结于 src/debate/research_scope.py。
前端仅对完整、唯一、复核未过期的同周期观点显示方向；insufficient 不等于中性；缺项、重复、周期不齐、失效时不给方向共识。每周期必须五个已完成且合格流派才可称方向一致，否则呈现缺口或分歧，不新加加权阈值。旧 vote_summary 保留兼容存储/内部流程，股票研究页面停止将其显示为方向共识或胜率。历史无 horizons 不推断、不改写。
review_on 为最迟复核日期，review_trigger 为提前复核条件，不代表预测保证有效到该日。起点为生成时北京时间，短/中/长期复核上限7/93/366自然日；交易日时长不转换为未核验的具体交易日期。全部为研究模式，未增加交易动作。

`AgentAnalysis.research_generated_at` 为服务端 ISO 时间，可空兼容旧记录；客户端以北京时间自然日校验复核日期，并每分钟重检日期状态。JSON持久化恢复保留日期与三周期条件。

### 2026-10-07 补证与观点分布

沿用已有三周期契约及方向准入；前端直接显示各周期有效看涨/看跌/中性数量，
分母为全部唯一流派，缺项、过期、重复身份与失败不作为中性或有效方向。
占比不是涨跌概率，不从整体 confidence 外推周期胜率。原共识规则保留。

API 创建的编排器在分析师之前主动补抓公司主营、最近年度/半年度报告节选、
合并财务事实与同期比较、近90天公司新闻/公告目录。全部复用已接入来源；
身份不一致拒绝注入、失败分支明确留缺口。它们是有限研究上下文，不能替换
行情、K线或交易门禁。旧历史记录保持原样，新请求使用新增上下文。

2026-10-07 后续：主动补证增加既有新浪/腾讯双源已结束RAW日线与MA/RSI/MACD/KDJ。
研究对象为backend/technical_research.py::TechnicalResearch，状态available/unavailable；
含stock_code、fetched_at、sources、diagnostics、bars、最近20根indicators、methodology、
limitations。此对象仅进入模型研究上下文，未新增HTTP契约；交易准入保持原规则。
