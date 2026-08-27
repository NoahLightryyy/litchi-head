"""KR-3B assembly boundary for verified market-data runtimes."""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from src.data.evidence import (
    EvidenceCapability,
    EvidenceEnvelope,
    SourceStatus,
)
from src.data.intraday import IntradayBar, IntradayBarState
from src.data.kline import MarketCode
from src.data.kline_adjustment import AdjustedKlineSeries
from src.data.kline_business import (
    FinalMinuteBar,
    KlineBusinessEnvelope,
    KlineBusinessFailure,
    KlineBusinessLayer,
    KlineBusinessResult,
    KlineLayerDiagnostic,
    KlineRetryDisposition,
    KlineSourceDiagnostic,
    LiveRawQuote,
    ProvisionalSessionBar,
    TradingPhase,
)
from src.data.models import StockQuote

SHANGHAI = ZoneInfo("Asia/Shanghai")

_SUCCESS_STATUSES = {SourceStatus.SUCCESS_DATA, SourceStatus.SUCCESS_EMPTY}
_STATUS_PRIORITY = {
    SourceStatus.CONFLICTED: 0,
    SourceStatus.STALE: 1,
    SourceStatus.FAILED: 2,
    SourceStatus.UNSUPPORTED: 3,
}
_STATUS_FALLBACK_CODE = {
    SourceStatus.CONFLICTED: "source_conflicted",
    SourceStatus.STALE: "source_stale",
    SourceStatus.FAILED: "source_failed",
    SourceStatus.UNSUPPORTED: "source_unsupported",
}
_STATUS_FALLBACK_MESSAGE = {
    SourceStatus.CONFLICTED: "Source evidence conflicts with another required fact",
    SourceStatus.STALE: "Source evidence is stale",
    SourceStatus.FAILED: "Source evidence collection failed",
    SourceStatus.UNSUPPORTED: "Source does not support the required evidence",
}
_WAIT_FOR_CONDITION_CODES = {
    "calendar_coverage_missing",
    "expected_trading_date_missing",
    "independent_upstream_missing",
    "kline_source_window_not_covered",
    "market_not_in_continuous_auction",
    "official_verification_unavailable",
    "security_status_coverage_missing",
}
_OPERATOR_ACTION_CODES = {
    "business_layer_validation_failed",
    "daily_snapshot_lineage_mismatch",
    "duplicate_trading_date",
    "instrument_identity_conflict",
    "intraday_cardinality_invalid",
    "intraday_final_minute_missing",
    "intraday_identity_conflict",
    "intraday_ohlc_missing",
    "invalid_request",
    "invalid_upstream_payload",
    "quote_cardinality_invalid",
    "quote_identity_conflict",
    "quote_ohlc_invalid",
    "quote_session_date_mismatch",
    "quote_timestamp_missing",
    "quote_timestamp_in_future",
    "trading_date_conflict",
    "trading_date_out_of_range",
    "unexpected_trading_date",
}


def _validate_runtime_requests(
    *,
    symbol: str,
    daily_evidence: EvidenceEnvelope,
    intraday_evidence: EvidenceEnvelope,
    quote_evidence: EvidenceEnvelope,
) -> None:
    expected_capabilities = (
        (daily_evidence, EvidenceCapability.KLINE),
        (intraday_evidence, EvidenceCapability.INTRADAY),
        (quote_evidence, EvidenceCapability.REALTIME_QUOTE),
    )
    if any(
        evidence.request.capability is not expected
        for evidence, expected in expected_capabilities
    ):
        raise ValueError("runtime evidence capability is wired to the wrong layer")
    if any(
        evidence.request.stock_code != symbol
        for evidence in (daily_evidence, intraday_evidence, quote_evidence)
    ):
        raise ValueError("runtime evidence symbol does not match business request")


def _source_diagnostics(evidence: EvidenceEnvelope) -> tuple[KlineSourceDiagnostic, ...]:
    diagnostics: list[KlineSourceDiagnostic] = []
    for result in evidence.source_results:
        if result.status in _SUCCESS_STATUSES:
            continue
        error_code = result.error_code or _STATUS_FALLBACK_CODE[result.status]
        error_message = result.error_message or _STATUS_FALLBACK_MESSAGE[result.status]
        diagnostics.append(
            KlineSourceDiagnostic(
                source_id=result.source_id,
                upstream_id=result.upstream_id,
                status=result.status,
                error_code=error_code,
                error_message=error_message,
                fetched_at=result.fetched_at,
            )
        )
    return tuple(sorted(diagnostics, key=lambda item: (item.source_id, item.upstream_id)))


def _primary_source_diagnostic(
    diagnostics: tuple[KlineSourceDiagnostic, ...],
) -> KlineSourceDiagnostic:
    return min(
        diagnostics,
        key=lambda item: (
            _STATUS_PRIORITY[item.status],
            item.error_code,
            item.upstream_id,
            item.source_id,
        ),
    )


def _retry_disposition(
    error_codes: tuple[str, ...],
    diagnostics: tuple[KlineSourceDiagnostic, ...],
) -> KlineRetryDisposition:
    all_codes = set(error_codes) | {item.error_code for item in diagnostics}
    if all_codes & _OPERATOR_ACTION_CODES:
        return KlineRetryDisposition.OPERATOR_ACTION
    if all_codes & _WAIT_FOR_CONDITION_CODES or any(
        item.status is SourceStatus.UNSUPPORTED for item in diagnostics
    ):
        return KlineRetryDisposition.WAIT_FOR_CONDITION
    return KlineRetryDisposition.RETRY_FRESH


def _complete_layer(
    layer: KlineBusinessLayer,
    evidence: EvidenceEnvelope,
) -> KlineLayerDiagnostic:
    return KlineLayerDiagnostic(
        layer=layer,
        complete=True,
        upstream_ids=tuple(sorted(evidence.assessment.successful_upstream_ids)),
    )


def _incomplete_layer(
    layer: KlineBusinessLayer,
    evidence: EvidenceEnvelope,
    *,
    error_code: str | None = None,
    error_message: str | None = None,
) -> KlineLayerDiagnostic:
    source_diagnostics = _source_diagnostics(evidence)
    if error_code is None and source_diagnostics:
        primary = _primary_source_diagnostic(source_diagnostics)
        error_code = primary.error_code
    if error_code is None:
        error_code = "independent_upstream_missing"
    if error_message is None:
        details = "; ".join(
            f"{item.source_id}/{item.upstream_id}: {item.error_code}: {item.error_message}"
            for item in source_diagnostics
        )
        missing = ",".join(sorted(evidence.assessment.missing_required_upstream_ids))
        if details and missing:
            error_message = f"{details}; missing required upstreams: {missing}"
        elif details:
            error_message = details
        elif missing:
            error_message = f"Missing required upstreams: {missing}"
        else:
            error_message = "Required independent market-data evidence is incomplete"
    return KlineLayerDiagnostic(
        layer=layer,
        complete=False,
        upstream_ids=tuple(sorted(evidence.assessment.successful_upstream_ids)),
        error_code=error_code,
        error_message=error_message,
        retry_disposition=_retry_disposition((error_code,), source_diagnostics),
        source_diagnostics=source_diagnostics,
    )


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
    _validate_runtime_requests(
        symbol=symbol,
        daily_evidence=daily_evidence,
        intraday_evidence=intraday_evidence,
        quote_evidence=quote_evidence,
    )
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


def assemble_kline_business(
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
) -> KlineBusinessResult:
    """Return a complete four-layer envelope or deterministic fail-closed diagnosis."""

    _validate_runtime_requests(
        symbol=symbol,
        daily_evidence=daily_evidence,
        intraday_evidence=intraday_evidence,
        quote_evidence=quote_evidence,
    )

    expected_identity = (symbol, market)
    session_date = as_of.astimezone(SHANGHAI).date()
    daily_identities = {(bar.code, bar.market) for bar in final_daily_bars.bars}
    if final_daily_bars.raw_snapshot_id != daily_snapshot_id:
        daily_diagnostic = _incomplete_layer(
            KlineBusinessLayer.FINAL_DAILY,
            daily_evidence,
            error_code="daily_snapshot_lineage_mismatch",
            error_message=(
                "Adjusted daily series raw snapshot does not match persisted daily evidence"
            ),
        )
    elif not daily_evidence.complete:
        daily_diagnostic = _incomplete_layer(
            KlineBusinessLayer.FINAL_DAILY,
            daily_evidence,
        )
    elif daily_identities != {expected_identity}:
        daily_diagnostic = _incomplete_layer(
            KlineBusinessLayer.FINAL_DAILY,
            daily_evidence,
            error_code="instrument_identity_conflict",
            error_message="Adjusted daily series identity does not match the request",
        )
    elif final_daily_bars.as_of > as_of:
        daily_diagnostic = _incomplete_layer(
            KlineBusinessLayer.FINAL_DAILY,
            daily_evidence,
            error_code="trading_date_out_of_range",
            error_message="Adjusted daily series timestamp exceeds the business as_of",
        )
    elif final_daily_bars.reference_date >= session_date:
        daily_diagnostic = _incomplete_layer(
            KlineBusinessLayer.FINAL_DAILY,
            daily_evidence,
            error_code="unexpected_trading_date",
            error_message="FINAL_DAILY must end before the active business session",
        )
    else:
        daily_diagnostic = _complete_layer(
            KlineBusinessLayer.FINAL_DAILY,
            daily_evidence,
        )

    final_minutes = tuple(
        item
        for item in intraday_evidence.items
        if isinstance(item, IntradayBar) and item.state is IntradayBarState.FINAL
    )
    if not intraday_evidence.complete:
        minute_diagnostic = _incomplete_layer(
            KlineBusinessLayer.FINAL_MINUTE,
            intraday_evidence,
        )
    elif not final_minutes:
        minute_diagnostic = _incomplete_layer(
            KlineBusinessLayer.FINAL_MINUTE,
            intraday_evidence,
            error_code="intraday_final_minute_missing",
            error_message="Complete intraday evidence contains no finalized minute",
        )
    elif any(bar.code != symbol for bar in final_minutes):
        minute_diagnostic = _incomplete_layer(
            KlineBusinessLayer.FINAL_MINUTE,
            intraday_evidence,
            error_code="intraday_identity_conflict",
            error_message="Finalized minute identity does not match the business request",
        )
    elif any(bar.timestamp > as_of for bar in final_minutes):
        minute_diagnostic = _incomplete_layer(
            KlineBusinessLayer.FINAL_MINUTE,
            intraday_evidence,
            error_code="trading_date_out_of_range",
            error_message="Finalized minute timestamp exceeds the business as_of",
        )
    elif any(bar.timestamp.astimezone(SHANGHAI).date() != session_date for bar in final_minutes):
        minute_diagnostic = _incomplete_layer(
            KlineBusinessLayer.FINAL_MINUTE,
            intraday_evidence,
            error_code="unexpected_trading_date",
            error_message="Finalized minutes must belong to the active business session",
        )
    elif tuple(bar.timestamp for bar in final_minutes) != tuple(
        sorted({bar.timestamp for bar in final_minutes})
    ):
        minute_diagnostic = _incomplete_layer(
            KlineBusinessLayer.FINAL_MINUTE,
            intraday_evidence,
            error_code="intraday_cardinality_invalid",
            error_message="Finalized minute timestamps must be unique and ordered",
        )
    else:
        minute_diagnostic = _complete_layer(
            KlineBusinessLayer.FINAL_MINUTE,
            intraday_evidence,
        )

    quotes = tuple(item for item in quote_evidence.items if isinstance(item, StockQuote))
    quote_error: tuple[str, str] | None = None
    if not quote_evidence.complete:
        pass
    elif len(quotes) != 1 or len(quote_evidence.items) != 1:
        quote_error = (
            "quote_cardinality_invalid",
            "Complete realtime quote evidence must contain exactly one canonical quote",
        )
    elif quotes[0].code != symbol:
        quote_error = (
            "quote_identity_conflict",
            "Canonical realtime quote identity does not match the business request",
        )
    elif (
        quotes[0].fetched_at is None
        or quotes[0].fetched_at.tzinfo is None
        or quotes[0].fetched_at.utcoffset() is None
    ):
        quote_error = (
            "quote_timestamp_missing",
            "Canonical realtime quote is missing its exchange timestamp",
        )
    elif quotes[0].fetched_at > as_of:
        quote_error = (
            "quote_timestamp_in_future",
            "Canonical realtime quote timestamp exceeds the business as_of",
        )
    elif quotes[0].fetched_at.astimezone(SHANGHAI).date() != session_date:
        quote_error = (
            "quote_session_date_mismatch",
            "Canonical realtime quote does not belong to the active business session",
        )
    elif (
        quotes[0].high < quotes[0].low
        or not quotes[0].low <= quotes[0].open_ <= quotes[0].high
        or not quotes[0].low <= quotes[0].price <= quotes[0].high
    ):
        quote_error = (
            "quote_ohlc_invalid",
            "Canonical realtime quote OHLC values are internally inconsistent",
        )

    if not quote_evidence.complete:
        live_quote_diagnostic = _incomplete_layer(
            KlineBusinessLayer.LIVE_QUOTE,
            quote_evidence,
        )
        provisional_diagnostic = _incomplete_layer(
            KlineBusinessLayer.PROVISIONAL,
            quote_evidence,
        )
    elif quote_error is not None:
        error_code, error_message = quote_error
        live_quote_diagnostic = _incomplete_layer(
            KlineBusinessLayer.LIVE_QUOTE,
            quote_evidence,
            error_code=error_code,
            error_message=error_message,
        )
        provisional_diagnostic = _incomplete_layer(
            KlineBusinessLayer.PROVISIONAL,
            quote_evidence,
            error_code=error_code,
            error_message=error_message,
        )
    else:
        live_quote_diagnostic = _complete_layer(
            KlineBusinessLayer.LIVE_QUOTE,
            quote_evidence,
        )
        provisional_diagnostic = _complete_layer(
            KlineBusinessLayer.PROVISIONAL,
            quote_evidence,
        )

    diagnostics = (
        daily_diagnostic,
        minute_diagnostic,
        live_quote_diagnostic,
        provisional_diagnostic,
    )
    incomplete = tuple(item for item in diagnostics if not item.complete)
    if incomplete:
        error_codes = tuple(
            dict.fromkeys(
                item.error_code for item in incomplete if item.error_code is not None
            )
        )
        return KlineBusinessFailure(
            symbol=symbol,
            market=market,
            as_of=as_of,
            trading_phase=trading_phase,
            error_codes=error_codes,
            layer_diagnostics=diagnostics,
        )

    return assemble_complete_kline_business(
        symbol=symbol,
        market=market,
        as_of=as_of,
        trading_phase=trading_phase,
        final_daily_bars=final_daily_bars,
        daily_snapshot_id=daily_snapshot_id,
        daily_evidence=daily_evidence,
        intraday_evidence=intraday_evidence,
        quote_evidence=quote_evidence,
    )


__all__ = ["assemble_complete_kline_business", "assemble_kline_business"]
