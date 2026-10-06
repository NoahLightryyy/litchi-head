"""Time-bounded research opinions, separate from unscoped legacy votes."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Horizon = Literal["short", "medium", "long"]


class HorizonOpinion(BaseModel):
    horizon: Horizon
    status: Literal["supported", "insufficient"]
    direction: Literal["Bullish", "Bearish", "Neutral"] | None
    thesis: str = Field(min_length=1, max_length=600)
    assumptions: list[str] = Field(min_length=1, max_length=5)
    invalidation: list[str] = Field(min_length=1, max_length=5)
    review_on: date
    review_trigger: str = Field(min_length=1, max_length=400)
    evidence: list[str] = Field(min_length=1, max_length=5)
    limitations: str = Field(min_length=1, max_length=600)

    @field_validator("assumptions", "invalidation", "evidence")
    @classmethod
    def meaningful_items(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("Research conditions must not be blank")
        return value


def scope_prompt(today: date) -> str:
    return f"""
【必须分别输出三个周期的条件研究】研究起点为北京时间 {today.isoformat()}。
在 horizons 中恰好输出 short（未来1–5个交易日）、medium（未来1–3个月）、
long（未来1–3年）各一项。均讨论该区间价格方向相对本次已提供报价的变化可能性，
不是保证收益、不是持仓建议。数据时间必须沿用输入，不能把收盘快照说成今天实时价格。
每项提供 thesis、assumptions（可观察的成立前提）、invalidation（可证伪的失效条件）、
review_on（明确复核日期，不能早于研究起点）、review_trigger（更早触发复核的事件）、
evidence（实际提供证据及其时间）、limitations（缺口）。不要凭空造目标价或阈值。
复核是重新审查，不是预测到期必兑现。短期复核须在7个自然日内，中期93日内，长期366日内。
没有支持该周期的资料时 status=insufficient、direction=null，说明需要补充什么；
不能以大师的长期投资风格代替该股票的长期证据。status=supported 才能给方向。
summary 与 analysis 只作三周期研究总述，不能再给一个混合周期买卖建议。
严禁将报价涨幅的参考基数自动认作前一交易日收盘价；新股首日可能是发行价。
未核验上市日期、参考价口径时，不能写“昨天21元今天65元”或由此推断派发。
半年财务累计不得当全年；市值或估值未提供时不得自行声称已知PE。
"""
