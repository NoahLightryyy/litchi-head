from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from backend.quote_display import get_display_quote
from src.data.evidence import EvidenceCapability, SourceResult, SourceStatus
from src.data.models import StockQuote
from src.data.providers.quotes import SHANGHAI


def result(source, *, failed=False, **changes):
    return SourceResult(
        source_id=f"direct-{source}-quote",
        upstream_id=source,
        capability=EvidenceCapability.REALTIME_QUOTE,
        status=SourceStatus.FAILED if failed else SourceStatus.SUCCESS_DATA,
        error_message="offline" if failed else None,
        items=[]
        if failed
        else [
            StockQuote(
                **{
                    "code": "920344",
                    "name": "三元基因",
                    "price": 24.35,
                    "change": 3.32,
                    "change_pct": 15.79,
                    "volume": 13381057,
                    "fetched_at": datetime(2026, 9, 30, 15, 30, tzinfo=SHANGHAI),
                    **changes,
                }
            )
        ],
    )


def test_bulk_failure_does_not_block_single_quote():
    with (
        patch(
            "backend.quote_display.EastmoneyQuoteSource.fetch",
            return_value=result("eastmoney", failed=True),
        ),
        patch("backend.quote_display.SinaQuoteSource.fetch", return_value=result("sina")),
    ):
        quote = get_display_quote("920344")
    assert quote is not None and quote.name == "三元基因"
    assert quote.source == "sina" and quote.fetched_at.day == 30
    assert quote.market_cap is None and quote.fund_flow is None


@pytest.mark.parametrize(
    "changes",
    [
        {"code": "000001"},
        {"name": " "},
        {"price": 0},
        {"fetched_at": None},
        {"fetched_at": datetime.now(SHANGHAI) + timedelta(days=1)},
    ],
)
def test_invalid_display_data_is_not_published(changes):
    with (
        patch(
            "backend.quote_display.EastmoneyQuoteSource.fetch",
            return_value=result("eastmoney", **changes),
        ),
        patch(
            "backend.quote_display.SinaQuoteSource.fetch", return_value=result("sina", failed=True)
        ),
    ):
        assert get_display_quote("920344") is None
