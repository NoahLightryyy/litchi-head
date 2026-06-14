"""风控模块 —— 三层风控辩论 + PM 最终裁决

R1 三层风控辩论：
    1. risk_round — Aggressive / Conservative / Neutral 三位风控官
    2. pm_round — Portfolio Manager 综合辩论 + 风控 → 最终 TradeRecommendation

交易纪律体系（行业对标）：
    - 买入纪律：证据门槛 / 分批建仓 / 事件窗口上限
    - 卖出纪律：双止损 / ATR 动态止损 / 三红线清仓
    - 仓位管理：三级上限 / 集中度上限 / 现金留存
    - 加仓减仓：盈利加仓 / 减仓信号 / 连亏熔断

用法:
    from src.risk.models import RiskAssessment, TradeRecommendation
    from src.risk.profiles import get_default_risk_officers
    from src.risk.orchestrator import make_risk_round_node, make_pm_round_node
"""

from src.risk.models import RiskAssessment, RiskRoundResult, TradeRecommendation
from src.risk.orchestrator import make_pm_round_node, make_risk_round_node
from src.risk.profiles import get_default_risk_officers

__all__ = [
    "RiskAssessment",
    "RiskRoundResult",
    "TradeRecommendation",
    "get_default_risk_officers",
    "make_risk_round_node",
    "make_pm_round_node",
]
