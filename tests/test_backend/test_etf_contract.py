from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.etf_contract import EtfIdentity, EtfQuote


def test_etf_market_identity_cannot_be_mixed():
    with pytest.raises(ValidationError):
        EtfIdentity(code="510050", symbol="sz510050", exchange="SH", name="上证50ETF")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 0, -1])
def test_etf_quote_rejects_invalid_price(value):
    with pytest.raises(ValidationError):
        EtfQuote(
            price=value,
            previous_close=2,
            change=0,
            change_pct=0,
            quoted_at=datetime.now(timezone.utc),
            source_name="ETF",
        )


def test_etf_quote_requires_timezone():
    with pytest.raises(ValidationError):
        EtfQuote(
            price=2,
            previous_close=2,
            change=0,
            change_pct=0,
            quoted_at=datetime(2026, 10, 9),
            source_name="ETF",
        )
