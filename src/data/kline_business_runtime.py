"""KR-3B assembly boundary for verified market-data runtimes."""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from src.data.evidence import EvidenceCapability, EvidenceEnvelope
from src.data.intraday import IntradayBar, IntradayBarState
from src.data.kline import MarketCode
from src.data.kline_adjustment import AdjustedKlineSeries
from src.data.kline_business import (
    FinalMinuteBar,
    KlineBusinessEnvelope,
    LiveRawQuote,
    ProvisionalSessionBar,
    TradingPhase,
)
from src.data.models import StockQuote

SHANGHAI = ZoneInfo("Asia/Shanghai")


def assemble_complete_kline_business(
    *,
    symbol: str,
    market: MarketCode,
    as_of: datetime,
    trading_phase: TradingPhase,
    final_daily_bars: AdjustedKlineSeries,
    daily_snapshot_id: str,
    daily_evidence: EvidenceEnvelope,
    intraday_evidence: EvidenceEnvelope,
    quote_evidence: EvidenceEnvelope,
) -> KlineBusinessEnvelope:
    """Assemble one complete business envelope from verified runtime evidence."""
    if final_daily_bars.raw_snapshot_id != daily_snapshot_id:
        raise ValueError("adjusted series daily snapshot lineage does not match evidence")
    if not all(
        evidence.complete for evidence in (daily_evidence, intraday_evidence, quote_evidence)
    ):
        raise ValueError("success assembly requires complete runtime evidence")
    expected_capabilities = (
        (daily_evidence, EvidenceCapability.KLINE),
        (intraday_evidence, EvidenceCapability.INTRADAY),
        (quote_evidence, EvidenceCapability.REALTIME_QUOTE),
    )
    if any(
        evidence.request.capability is not expected for evidence, expected in expected_capabilities
    ):
        raise ValueError("runtime evidence capability is wired to the wrong layer")
    if any(
        evidence.request.stock_code != symbol
        for evidence in (daily_evidence, intraday_evidence, quote_evidence)
    ):
        raise ValueError("runtime evidence symbol does not match business request")
    quotes = tuple(item for item in quote_evidence.items if isinstance(item, StockQuote))
    if len(quotes) != 1 or len(quote_evidence.items) != 1:
        raise ValueError("success assembly requires exactly one canonical realtime quote")
    quote = quotes[0]
    if quote.fetched_at is None:
        raise ValueError("complete realtime quote evidence requires fetched_at")
    final_minutes = tuple(
        FinalMinuteBar.model_validate(item.model_dump())
        for item in intraday_evidence.items
        if isinstance(item, IntradayBar) and item.state is IntradayBarState.FINAL
    )
    live_quote = LiveRawQuote.model_validate(quote.model_dump())
    quote_upstream_ids = tuple(sorted(quote_evidence.assessment.successful_upstream_ids))
    return KlineBusinessEnvelope(
        symbol=symbol,
        market=market,
        as_of=as_of,
        trading_phase=trading_phase,
        final_daily_bars=final_daily_bars,
        daily_upstream_ids=tuple(sorted(daily_evidence.assessment.successful_upstream_ids)),
        final_minute_bars=final_minutes,
        intraday_upstream_ids=tuple(sorted(intraday_evidence.assessment.successful_upstream_ids)),
        live_quote=live_quote,
        quote_upstream_ids=quote_upstream_ids,
        provisional_session_bar=ProvisionalSessionBar(
            code=symbol,
            market=market,
            trading_date=as_of.astimezone(SHANGHAI).date(),
            as_of=quote.fetched_at,
            trading_phase=trading_phase,
            open=Decimal(str(quote.open_)),
            high=Decimal(str(quote.high)),
            low=Decimal(str(quote.low)),
            close=Decimal(str(quote.price)),
            cumulative_volume=quote.volume,
            cumulative_amount=Decimal(str(quote.amount)),
            upstream_ids=quote_upstream_ids,
        ),
    )


__all__ = ["assemble_complete_kline_business"]
