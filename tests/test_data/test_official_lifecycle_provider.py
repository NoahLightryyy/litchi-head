"""Official SSE/SZSE security lifecycle adapter tests."""

import io
from datetime import date
from typing import Any

import pandas as pd
import pytest

from src.data.kline import MarketCode
from src.data.providers import lifecycle as lifecycle_provider
from src.data.providers.lifecycle import (
    OfficialLifecycleSnapshot,
    OfficialSecurityLifecycleSource,
    SecurityLifecycleSourceError,
)


class _Response:
    def __init__(
        self,
        *,
        content: bytes,
        payload: object | None = None,
    ) -> None:
        self.content = content
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload


def _xlsx(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_excel(buffer, index=False)
    return buffer.getvalue()


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


def test_default_sse_parser_reads_official_json_and_hashes_raw_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = b'{"official":"sse-active"}'
    payload = {
        "result": [
            {
                "A_STOCK_CODE": "600000",
                "LIST_DATE": "19991110",
                "DELIST_DATE": "-",
            }
        ]
    }

    def fake_get(*_: object, **kwargs: Any) -> _Response:
        assert kwargs["params"]["COMPANY_STATUS"] == "2,4,5,7,8"
        return _Response(content=raw, payload=payload)

    monkeypatch.setattr("httpx.get", fake_get)

    result = OfficialSecurityLifecycleSource().fetch(
        code="600000",
        market=MarketCode.SSE,
    )

    assert result.listed_on == date(1999, 11, 10)
    assert result.delisted_on is None
    assert result.source_url == lifecycle_provider.SSE_ACTIVE_PAGE_URL
    assert len(result.content_hash) == 64


def test_default_szse_parser_falls_back_to_official_delisted_xlsx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = _xlsx(
        pd.DataFrame(
            columns=["A股代码", "A股上市日期"],
        )
    )
    delisted = _xlsx(
        pd.DataFrame(
            [
                {
                    "证券代码": 13,
                    "上市日期": "1992-05-06",
                    "终止上市日期": "2004-09-20",
                }
            ]
        )
    )

    def fake_get(*_: object, **kwargs: Any) -> _Response:
        is_delisted = kwargs["params"]["CATALOGID"] == "1793_ssgs"
        return _Response(content=delisted if is_delisted else active)

    monkeypatch.setattr("httpx.get", fake_get)

    result = OfficialSecurityLifecycleSource().fetch(
        code="000013",
        market=MarketCode.SZSE,
    )

    assert result.listed_on == date(1992, 5, 6)
    assert result.delisted_on == date(2004, 9, 20)
    assert result.source_url == lifecycle_provider.SZSE_DELISTED_PAGE_URL


def test_malformed_default_official_response_is_visible_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "httpx.get",
        lambda *_args, **_kwargs: _Response(
            content=b"{}",
            payload={},
        ),
    )

    with pytest.raises(
        SecurityLifecycleSourceError,
        match="incomplete",
    ):
        OfficialSecurityLifecycleSource().fetch(
            code="600000",
            market=MarketCode.SSE,
        )
