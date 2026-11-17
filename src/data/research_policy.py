"""Market research availability, independent of stricter execution/audit policies."""
from src.data.evidence import EvidenceCapability, EvidencePolicy

RESEARCH_QUOTE_POLICY = EvidencePolicy(
    capability=EvidenceCapability.REALTIME_QUOTE, min_independent_upstreams=1,
)
RESEARCH_KLINE_POLICY = EvidencePolicy(
    capability=EvidenceCapability.KLINE, min_independent_upstreams=1,
)

MARKET_RESEARCH_PROMPT = (
    "【行情可用性规则】一个有效行情来源就足够用于研究和条件分析；多源用于故障备用，"
    "不是必须凑齐的门槛。来源数量本身不是风险，不得仅因单源、未交叉验证或备用源失败"
    "降低评分/置信度、判定insufficient、清空方向或拒绝提出条件计划。"
    "只在依据处保留实际来源和数据时间，不在各周期limitations重复列单源警告。"
    "历史分析若把单源视为缺证，该理由已不适用；不得把旧理由当作本轮规则。"
    "仍须检查标的身份、正数有效价格、时间、实际样本长度、复权口径及真实价格冲突。"
    "数据可用不等于看涨或可以买；资料确实不足、机会未出现仍须明确具体原因。"
    "不得把单源称为多源已验证，不保证各网站所有时点、复权与成交量口径都相同。"
)
