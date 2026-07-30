"""Official SSE/SZSE security lifecycle adapter tests."""

from datetime import date

import pytest

from src.data.kline import MarketCode
from src.data.providers.lifecycle import (
    OfficialLifecycleSnapshot,
    OfficialSecurityLifecycleSource,
    SecurityLifecycleSourceError,
)


def _snapshot(
    *,
    code: str = "600000",
    listed_on: date = date(1999, 11, 10),
    delisted_on: date | None = None,
    suffix: str = "active",
) -> OfficialLifecycleSnapshot:
    return OfficialLifecycleSnapshot(
        code=code,
        listed_on=listed_on,
        delisted_on=delisted_on,
        source_url=f"https://www.sse.com.cn/official/{suffix}",
        content_hash=suffix[0] * 64,
    )


def test_active_sse_security_uses_official_listing_snapshot() -> None:
    calls: list[tuple[MarketCode, bool]] = []

    def fetcher(
        market: MarketCode,
        delisted: bool,
    ) -> tuple[OfficialLifecycleSnapshot, ...]:
        calls.append((market, delisted))
        return (_snapshot(),) if not delisted else ()

    lifecycle = OfficialSecurityLifecycleSource(fetcher=fetcher).fetch(
        code="600000",
        market=MarketCode.SSE,
    )

    assert lifecycle.code == "600000"
    assert lifecycle.market is MarketCode.SSE
    assert lifecycle.listed_on == date(1999, 11, 10)
    assert lifecycle.delisted_on is None
    assert lifecycle.source_url.endswith("/active")
    assert lifecycle.content_hash == "a" * 64
    assert calls == [(MarketCode.SSE, False)]


def test_delisted_szse_security_falls_back_to_official_delisting_snapshot() -> None:
    calls: list[tuple[MarketCode, bool]] = []

    def fetcher(
        market: MarketCode,
        delisted: bool,
    ) -> tuple[OfficialLifecycleSnapshot, ...]:
        calls.append((market, delisted))
        if delisted:
            return (
                _snapshot(
                    code="000013",
                    listed_on=date(1992, 5, 6),
                    delisted_on=date(2004, 9, 20),
                    suffix="delisted",
                ),
            )
        return ()

    lifecycle = OfficialSecurityLifecycleSource(fetcher=fetcher).fetch(
        code="000013",
        market=MarketCode.SZSE,
    )

    assert lifecycle.market is MarketCode.SZSE
    assert lifecycle.listed_on == date(1992, 5, 6)
    assert lifecycle.delisted_on == date(2004, 9, 20)
    assert calls == [
        (MarketCode.SZSE, False),
        (MarketCode.SZSE, True),
    ]


def test_missing_or_duplicate_official_identity_fails_closed() -> None:
    source = OfficialSecurityLifecycleSource(fetcher=lambda *_: ())

    with pytest.raises(SecurityLifecycleSourceError, match="not found"):
        source.fetch(code="600000", market=MarketCode.SSE)

    duplicate = OfficialSecurityLifecycleSource(
        fetcher=lambda *_: (_snapshot(), _snapshot(suffix="another"))
    )
    with pytest.raises(SecurityLifecycleSourceError, match="duplicate"):
        duplicate.fetch(code="600000", market=MarketCode.SSE)


def test_rejects_unverified_bse_lifecycle_path() -> None:
    source = OfficialSecurityLifecycleSource(fetcher=lambda *_: ())

    with pytest.raises(SecurityLifecycleSourceError, match="BSE"):
        source.fetch(code="920176", market=MarketCode.BSE)
