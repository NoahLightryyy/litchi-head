"""KR-4A adapter from the frozen K-line business result to debate context."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from src.data.evidence import SourceStatus
from src.data.kline_business import (
    KlineBusinessEnvelope,
    KlineBusinessFailure,
    KlineBusinessResult,
    KlineRetryDisposition,
)
from src.debate.models import EvidenceLimitation, EvidenceReference

KlineBusinessProvider = Callable[[str], KlineBusinessResult]


def classify_kline_business_result(
    result: KlineBusinessResult,
) -> Literal["complete", "limited", "blocked"]:
    """Classify without reinterpreting prices, sources, or tolerances."""
    if isinstance(result, KlineBusinessEnvelope):
        return "complete"
    if any(
        diagnostic.retry_disposition is KlineRetryDisposition.OPERATOR_ACTION
        or any(
            source.status is SourceStatus.CONFLICTED
            for source in diagnostic.source_diagnostics
        )
        for diagnostic in result.layer_diagnostics
        if not diagnostic.complete
    ):
        return "blocked"
    return "limited"


def kline_failure_limitation(
    failure: KlineBusinessFailure,
) -> dict[str, object]:
    """Convert a retryable four-layer failure into a structured disclosure."""
    incomplete = tuple(item for item in failure.layer_diagnostics if not item.complete)
    missing_upstreams = sorted(
        {
            source.upstream_id
            for diagnostic in incomplete
            for source in diagnostic.source_diagnostics
        }
    )
    source_statuses = {
        source.source_id: source.status.value
        for diagnostic in incomplete
        for source in diagnostic.source_diagnostics
    }
    retry_dispositions = {
        diagnostic.layer.value: diagnostic.retry_disposition.value
        for diagnostic in incomplete
        if diagnostic.retry_disposition is not None
    }
    limitation = EvidenceLimitation(
        capability="kline_business",
        missing_upstream_ids=missing_upstreams,
        missing_independent_upstreams=len(missing_upstreams),
        source_statuses=dict(sorted(source_statuses.items())),
        collected_at=failure.as_of,
        affected_layers=[diagnostic.layer.value for diagnostic in incomplete],
        error_codes=list(failure.error_codes),
        retry_dispositions=retry_dispositions,
    )
    return limitation.model_dump(mode="json")


def kline_evidence_reference(
    envelope: KlineBusinessEnvelope,
) -> dict[str, object]:
    """Build the immutable result/memory reference for one complete input."""
    reference = EvidenceReference(
        capability="kline_business",
        symbol=envelope.symbol,
        market=envelope.market.value,
        as_of=envelope.as_of,
        trading_phase=envelope.trading_phase.value,
        raw_snapshot_id=envelope.final_daily_bars.raw_snapshot_id,
        factor_version=envelope.final_daily_bars.factor_version,
        reference_date=envelope.final_daily_bars.reference_date,
        price_basis=envelope.live_quote.price_basis,
        daily_upstream_ids=list(envelope.daily_upstream_ids),
        intraday_upstream_ids=list(envelope.intraday_upstream_ids),
        quote_upstream_ids=list(envelope.quote_upstream_ids),
    )
    return reference.model_dump(mode="json")


def format_kline_business_context(envelope: KlineBusinessEnvelope) -> str:
    """Render four visibly separate, coordinate-safe prompt sections."""
    daily_lines = [
        (
            f"  {bar.trade_date.isoformat()} O={bar.open} H={bar.high} "
            f"L={bar.low} C={bar.close} V={bar.volume} A={bar.amount}"
        )
        for bar in envelope.final_daily_bars.bars
    ]
    minute_lines = [
        (
            f"  {bar.timestamp.isoformat()} O={bar.open:.4f} H={bar.high:.4f} "
            f"L={bar.low:.4f} C={bar.close:.4f} V={bar.volume} A={bar.amount:.2f}"
        )
        for bar in envelope.final_minute_bars
    ]
    quote = envelope.live_quote
    provisional = envelope.provisional_session_bar
    return "\n".join(
        [
            "📐 K 线四层证据（各层不得混装或互换价格坐标）",
            f"as_of={envelope.as_of.isoformat()} | phase={envelope.trading_phase.value}",
            "FINAL_DAILY（QFQ，仅用于历史结构）",
            (
                f"  snapshot={envelope.final_daily_bars.raw_snapshot_id} | "
                f"factor={envelope.final_daily_bars.factor_version} | "
                f"reference_date={envelope.final_daily_bars.reference_date.isoformat()} | "
                f"upstreams={','.join(envelope.daily_upstream_ids)}"
            ),
            *daily_lines,
            "FINAL_MINUTE（RAW，已结束分钟）",
            f"  upstreams={','.join(envelope.intraday_upstream_ids)}",
            *minute_lines,
            "LIVE_QUOTE（RAW，成交/订单价格坐标）",
            (
                f"  at={quote.fetched_at.isoformat() if quote.fetched_at else 'missing'} | "
                f"price={quote.price:.4f} | O={quote.open_:.4f} H={quote.high:.4f} "
                f"L={quote.low:.4f} | upstreams={','.join(envelope.quote_upstream_ids)}"
            ),
            "PROVISIONAL（RAW，未确认收盘）",
            (
                f"  date={provisional.trading_date.isoformat()} | "
                f"at={provisional.as_of.isoformat()} | "
                f"O={provisional.open} H={provisional.high} L={provisional.low} "
                f"C={provisional.close} V={provisional.cumulative_volume}"
            ),
            "约束：PROVISIONAL 不能表述为正式收盘、正式突破或已确认日线形态；"
            "QFQ 数值不能作为成交、订单、止损或止盈价格。",
        ]
    )


__all__ = [
    "KlineBusinessProvider",
    "classify_kline_business_result",
    "format_kline_business_context",
    "kline_evidence_reference",
    "kline_failure_limitation",
]
