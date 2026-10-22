from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, localcontext

import pytest

from src.backtest.e0.models import (
    DecisionAction,
    E0Sample,
    FrozenEvidence,
    MarketRegime,
    RunnerContext,
    RunnerId,
)
from src.backtest.e0.runners import (
    BuyHoldRunner,
    CashRunner,
    E0Runner,
    E0RunnerEvidenceError,
    Momentum20Runner,
)

DECISION_AT = datetime(2026, 1, 30, 7, 0, tzinfo=UTC)
HASH = f"sha256:{'a' * 64}"


def _sample(*, entry_tradable: bool = True) -> E0Sample:
    return E0Sample(
        sample_id="e0-fixture:candidate-001",
        candidate_id="candidate-001",
        symbol="000001",
        decision_at=DECISION_AT,
        regime=MarketRegime.UP,
        evidence_snapshot_id="evidence-001",
        evidence_hash=HASH,
        entry_tradable=entry_tradable,
    )


def _bar(trade_date: date, close: Decimal) -> dict[str, object]:
    price = str(close)
    return {
        "date": trade_date.isoformat(),
        "open": price,
        "close": price,
        "high": price,
        "low": price,
        "volume": 1000,
        "amount": "10000",
        "fetched_at": None,
    }


def _evidence(
    closes: tuple[Decimal, ...] = (Decimal("100"),) * 21,
    *,
    final_bar_date: date | None = None,
    as_of: datetime = DECISION_AT - timedelta(minutes=1),
) -> FrozenEvidence:
    first_day = DECISION_AT.date() - timedelta(days=len(closes) + 1)
    bars = [
        _bar(first_day + timedelta(days=index), close)
        for index, close in enumerate(closes)
    ]
    if final_bar_date is not None:
        bars[-1] = _bar(final_bar_date, closes[-1])
    return FrozenEvidence(
        sample_id="e0-fixture:candidate-001",
        symbol="000001",
        as_of=as_of,
        evidence_snapshot_id="evidence-001",
        evidence_hash=HASH,
        quote_json=json.dumps({"price": "100"}),
        completed_klines_json=json.dumps(bars),
        news_json="[]",
        financials_json="{}",
        industry_json="{}",
        sentiment_json="{}",
    )


def _context(runner_id: RunnerId) -> RunnerContext:
    return RunnerContext(
        experiment_id="e0-fixture",
        sample_id="e0-fixture:candidate-001",
        runner_id=runner_id,
        repetition=1,
        position_fraction=Decimal("0.25"),
        model_id="not-applicable",
        decision_question="未来五个交易日是否应持有该股票？",
        prompt_version="not-applicable:v1",
        timeout_seconds=Decimal("30"),
    )


@pytest.mark.asyncio
async def test_cash_runner_never_trades() -> None:
    runner: E0Runner = CashRunner(version="cash:v1")

    result = await runner.run(_sample(), _evidence(), _context(RunnerId.B0))

    assert runner.runner_id is RunnerId.B0
    assert result.action is DecisionAction.CASH
    assert result.position_fraction == Decimal("0")
    assert result.confidence is None
    assert result.error_code is None
    assert result.input_tokens == result.output_tokens == 0
    assert result.model_cost == Decimal("0")


@pytest.mark.parametrize(
    ("entry_tradable", "expected_action", "expected_position"),
    [
        (True, DecisionAction.LONG, Decimal("0.25")),
        (False, DecisionAction.CASH, Decimal("0")),
    ],
)
@pytest.mark.asyncio
async def test_buy_hold_uses_frozen_entry_proof_and_manifest_position(
    entry_tradable: bool,
    expected_action: DecisionAction,
    expected_position: Decimal,
) -> None:
    result = await BuyHoldRunner(version="buy-hold:v1").run(
        _sample(entry_tradable=entry_tradable),
        _evidence(),
        _context(RunnerId.B1),
    )

    assert result.action is expected_action
    assert result.position_fraction == expected_position


@pytest.mark.parametrize(
    ("last_close", "expected_action"),
    [
        (Decimal("101"), DecisionAction.LONG),
        (Decimal("100"), DecisionAction.CASH),
        (Decimal("99"), DecisionAction.CASH),
    ],
)
@pytest.mark.asyncio
async def test_momentum_rule_is_positive_20_session_return_only(
    last_close: Decimal,
    expected_action: DecisionAction,
) -> None:
    closes = (Decimal("100"),) * 20 + (last_close,)

    result = await Momentum20Runner(version="momentum20:v1").run(
        _sample(),
        _evidence(closes),
        _context(RunnerId.B3),
    )

    assert result.action is expected_action
    assert result.position_fraction == (
        Decimal("0.25") if expected_action is DecisionAction.LONG else Decimal("0")
    )


@pytest.mark.asyncio
async def test_momentum_rule_ignores_ambient_decimal_precision() -> None:
    closes = (Decimal("100"),) * 20 + (Decimal(f"100.{'0' * 40}1"),)
    runner = Momentum20Runner(version="momentum20:v1")

    with localcontext() as low_precision:
        low_precision.prec = 6
        low_result = await runner.run(
            _sample(), _evidence(closes), _context(RunnerId.B3)
        )
    with localcontext() as high_precision:
        high_precision.prec = 50
        high_result = await runner.run(
            _sample(), _evidence(closes), _context(RunnerId.B3)
        )

    assert low_result.action is high_result.action is DecisionAction.LONG


@pytest.mark.asyncio
async def test_momentum_rule_rejects_non_finite_close_string() -> None:
    closes = (Decimal("100"),) * 20 + (Decimal("Infinity"),)

    with pytest.raises(E0RunnerEvidenceError) as exc_info:
        await Momentum20Runner(version="momentum20:v1").run(
            _sample(),
            _evidence(closes),
            _context(RunnerId.B3),
        )

    assert exc_info.value.code == "completed_bar_price_invalid"


@pytest.mark.parametrize("runner_id", [RunnerId.B1, RunnerId.B3])
@pytest.mark.asyncio
async def test_market_baselines_reject_incomplete_historical_window(
    runner_id: RunnerId,
) -> None:
    runner = (
        BuyHoldRunner(version="buy-hold:v1")
        if runner_id is RunnerId.B1
        else Momentum20Runner(version="momentum20:v1")
    )

    with pytest.raises(E0RunnerEvidenceError) as exc_info:
        await runner.run(
            _sample(),
            _evidence((Decimal("100"),) * 20),
            _context(runner_id),
        )

    assert exc_info.value.code == "insufficient_completed_bars"


@pytest.mark.parametrize("runner_id", [RunnerId.B1, RunnerId.B3])
@pytest.mark.asyncio
async def test_market_baselines_reject_post_decision_label_bar(
    runner_id: RunnerId,
) -> None:
    runner = (
        BuyHoldRunner(version="buy-hold:v1")
        if runner_id is RunnerId.B1
        else Momentum20Runner(version="momentum20:v1")
    )

    with pytest.raises(E0RunnerEvidenceError) as exc_info:
        await runner.run(
            _sample(),
            _evidence(final_bar_date=DECISION_AT.date()),
            _context(runner_id),
        )

    assert exc_info.value.code == "future_bar_forbidden"


@pytest.mark.parametrize("runner_id", [RunnerId.B1, RunnerId.B3])
@pytest.mark.asyncio
async def test_market_baselines_reject_bars_after_evidence_as_of(
    runner_id: RunnerId,
) -> None:
    runner = (
        BuyHoldRunner(version="buy-hold:v1")
        if runner_id is RunnerId.B1
        else Momentum20Runner(version="momentum20:v1")
    )

    with pytest.raises(E0RunnerEvidenceError) as exc_info:
        await runner.run(
            _sample(),
            _evidence(as_of=DECISION_AT - timedelta(days=10)),
            _context(runner_id),
        )

    assert exc_info.value.code == "bar_after_evidence_as_of"


@pytest.mark.asyncio
async def test_baseline_rejects_mismatched_frozen_evidence_identity() -> None:
    evidence = _evidence().model_copy(update={"sample_id": "another-sample"})

    with pytest.raises(E0RunnerEvidenceError) as exc_info:
        await CashRunner(version="cash:v1").run(
            _sample(), evidence, _context(RunnerId.B0)
        )

    assert exc_info.value.code == "evidence_identity_mismatch"


@pytest.mark.asyncio
async def test_baseline_rejects_mismatched_experiment_identity() -> None:
    context = _context(RunnerId.B0).model_copy(
        update={"experiment_id": "wrong-experiment"}
    )

    with pytest.raises(E0RunnerEvidenceError) as exc_info:
        await CashRunner(version="cash:v1").run(_sample(), _evidence(), context)

    assert exc_info.value.code == "runner_context_mismatch"
