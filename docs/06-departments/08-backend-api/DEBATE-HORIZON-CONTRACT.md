# 三周期条件研究契约（2026-10-06）
用户确认每次同时研究 short（1–5交易日）、medium（1–3个月）、long（1–3年），不合成跨周期方向。
AgentAnalysis 新增 horizons（默认空数组兼容历史），每项：horizon；status supported/insufficient；direction Bullish/Bearish/Neutral/null；thesis；assumptions[]；invalidation[]；review_on ISO日期；review_trigger；evidence[]；limitations。Pydantic HorizonOpinion 冻结于 src/debate/research_scope.py。
前端仅对完整、唯一、复核未过期的同周期观点显示方向；insufficient 不等于中性；缺项、重复、周期不齐、失效时不给方向共识。每周期必须五个已完成且合格流派才可称方向一致，否则呈现缺口或分歧，不新加加权阈值。旧 vote_summary 保留兼容存储/内部流程，股票研究页面停止将其显示为方向共识或胜率。历史无 horizons 不推断、不改写。
review_on 为最迟复核日期，review_trigger 为提前复核条件，不代表预测保证有效到该日。起点为生成时北京时间，短/中/长期复核上限7/93/366自然日；交易日时长不转换为未核验的具体交易日期。全部为研究模式，未增加交易动作。
