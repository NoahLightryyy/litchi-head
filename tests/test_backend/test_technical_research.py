"""Independent formula fixtures and rejection of incomplete technical evidence."""
from datetime import UTC, date, datetime, timedelta

import pytest

from backend.indicators import calc_all, calc_kdj, calc_rsi
from backend.technical_research import build_technical_research
from src.data.evidence import (
    EvidenceAssessment,
    EvidenceCapability,
    EvidenceEnvelope,
    EvidenceRequest,
)
from src.data.kline import RawDailyBar
from src.data.kline_runtime import KLINE_RAW_EVIDENCE_POLICY


def test_kdj_full_window_seed_and_unclipped_j() -> None:
    rows = [{"high": 10, "low": 0, "close": 10} for _ in range(12)]
    result = calc_kdj(rows)
    assert result["k"][:8] == [None] * 8
    assert result["k"][8] == pytest.approx(200 / 3)
    assert result["d"][8] == pytest.approx(500 / 9)
    assert result["j"][8] == pytest.approx(800 / 9)
    assert result["j"][-1] > 100
    assert calc_kdj([]) == {"k": [], "d": [], "j": []}
    with pytest.raises(ValueError):
        calc_kdj(rows, 0)


def test_flat_prices_are_neutral_not_overbought() -> None:
    rows = [{"high": 10, "low": 10, "close": 10} for _ in range(60)]
    assert calc_rsi(rows)[-1] == 50
    assert all(values[-1] == 50 for values in calc_kdj(rows).values())
    result = calc_all(rows)
    assert result["ma"]["ma60"] == 10
    assert result["macd"] == {"value": 0, "signal": 0, "histogram": 0}


def envelope(complete: bool = True, code: str = "300893") -> EvidenceEnvelope:
    bars = [RawDailyBar(code=code, market="SZSE", trade_date=date(2026, 1, 1) + timedelta(days=i),
                        open=10, high=10, low=10, close=10, volume=100)
            for i in range(60)]
    return EvidenceEnvelope(
        request=EvidenceRequest(capability=EvidenceCapability.KLINE, stock_code=code),
        policy=KLINE_RAW_EVIDENCE_POLICY, items=bars, complete=complete,
        assessment=EvidenceAssessment(capability=EvidenceCapability.KLINE, complete=complete,
            successful_upstream_ids={"sina", "tencent"} if complete else set(),
            missing_independent_upstreams=0 if complete else 2),
        collected_at=datetime(2026, 10, 7, tzinfo=UTC),
    )


def test_complete_history_calculates_before_tail_selection() -> None:
    result = build_technical_research("300893", envelope())
    assert result.sources == ["sina", "tencent"]
    assert len(result.bars) == 60 and len(result.indicators) == 20
    assert result.indicators[-1].ma["ma60"] == 10
    assert result.indicators[0].ma["ma60"] is None
    assert result.indicators[-1].kdj["j"] == 50
    assert result.price_basis == "raw"
    assert "未复权" in result.limitations[0]


def test_conflicted_history_never_computes_indicators() -> None:
    result = build_technical_research("300893", envelope(False))
    assert result.status == "unavailable"
    assert not result.bars and not result.indicators


def test_foreign_or_duplicate_bars_rejected() -> None:
    with pytest.raises(ValueError, match="identity"):
        build_technical_research("300893", envelope(code="000001"))
    data = envelope()
    data.items.append(data.items[-1])
    with pytest.raises(ValueError, match="Duplicate"):
        build_technical_research("300893", data)
