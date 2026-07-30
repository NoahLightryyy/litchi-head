"""Official SSE/SZSE security lifecycle adapter tests."""

import io
import json
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

    @property
    def text(self) -> str:
        return self.content.decode("utf-8")


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


def _jsonp(payload: object) -> bytes:
    return f"lhcb({json.dumps(payload, ensure_ascii=False)})".encode()


def _bse_page(
    rows: list[dict[str, object]],
    *,
    number: int = 0,
    total_pages: int = 1,
    total_elements: int | None = None,
) -> dict[str, object]:
    count = len(rows) if total_elements is None else total_elements
    return {
        "content": rows,
        "firstPage": number == 0,
        "lastPage": total_pages == 0 or number == total_pages - 1,
        "number": number,
        "numberOfElements": len(rows),
        "size": 20,
        "sort": None,
        "totalElements": count,
        "totalPages": total_pages,
    }


def _bse_mapping_html(
    *,
    listed_on: str = "2021/8/26",
    old_code: str = "835305",
    new_code: str = "920305",
) -> bytes:
    return (
        "<table><tr><th>序号</th><th>证券简称</th><th>上市日期</th>"
        "<th>旧代码</th><th>新代码</th></tr>"
        f"<tr><td>1</td><td>云创数据</td><td>{listed_on}</td>"
        f"<td>{old_code}</td><td>{new_code}</td></tr></table>"
    ).encode()


def test_active_bse_security_uses_complete_official_listing_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {
        "xxzqdm": "920176",
        "xxzqjc": "维琪科技",
        "fxssrq": "20260727",
        "xxfcbj": "2",
    }

    def fake_get(url: str, *_: object, **kwargs: Any) -> _Response:
        if url == lifecycle_provider.BSE_CODE_MAPPING_URL:
            return _Response(content=_bse_mapping_html())
        assert url == lifecycle_provider.BSE_LIST_QUERY_URL
        assert ("xxfcbj[]", "2") in kwargs["params"]
        return _Response(content=_jsonp([_bse_page([row])]))

    monkeypatch.setattr("httpx.get", fake_get)

    lifecycle = OfficialSecurityLifecycleSource().fetch(
        code="920176",
        market=MarketCode.BSE,
    )

    assert lifecycle.listed_on == date(2026, 7, 27)
    assert lifecycle.delisted_on is None
    assert lifecycle.source_url == lifecycle_provider.BSE_LISTED_COMPANY_PAGE_URL
    assert len(lifecycle.content_hash) == 64


def test_delisted_bse_security_uses_mapping_and_official_termination_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = _jsonp([_bse_page([], total_pages=0)])
    delisted = _jsonp(
        [
            [_bse_page(
                [
                    {
                        "comments": "",
                        "companycode": "920305",
                        "companyname": "云创退",
                        "productType": "10",
                        "publishdate": "2026-07-30",
                        "typecode": "1101",
                        "typename": "退市/摘牌",
                        "xxfcbj": "2",
                        "xxzqjb": "T",
                    }
                ]
            )],
            [{"typecode": "1101", "num": 1, "typename": "退市/摘牌"}],
            "2021-11-15",
            "2026-07-30",
        ]
    )

    def fake_get(url: str, *_: object, **__: Any) -> _Response:
        if url == lifecycle_provider.BSE_LIST_QUERY_URL:
            return _Response(content=active)
        if url == lifecycle_provider.BSE_CODE_MAPPING_URL:
            return _Response(content=_bse_mapping_html())
        assert url == lifecycle_provider.BSE_TRADING_TIPS_QUERY_URL
        return _Response(content=delisted)

    monkeypatch.setattr("httpx.get", fake_get)

    lifecycle = OfficialSecurityLifecycleSource().fetch(
        code="920305",
        market=MarketCode.BSE,
    )

    assert lifecycle.listed_on == date(2021, 8, 26)
    assert lifecycle.delisted_on == date(2026, 7, 30)
    assert lifecycle.source_url == lifecycle_provider.BSE_MARKET_CALENDAR_PAGE_URL


def test_bse_lifecycle_rejects_incomplete_advertised_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _jsonp(
        [_bse_page(
            [
                {
                    "xxzqdm": "920176",
                    "fxssrq": "20260727",
                    "xxfcbj": "2",
                }
            ],
            total_pages=2,
            total_elements=2,
        )]
    )
    broken_second = _jsonp(
        [_bse_page([], number=1, total_pages=2, total_elements=2)]
    )

    def fake_get(url: str, *_: object, **kwargs: Any) -> _Response:
        if url == lifecycle_provider.BSE_CODE_MAPPING_URL:
            return _Response(content=_bse_mapping_html())
        page = int(dict(kwargs["params"])["page"])
        return _Response(content=first if page == 0 else broken_second)

    monkeypatch.setattr("httpx.get", fake_get)

    with pytest.raises(SecurityLifecycleSourceError, match="pagination"):
        OfficialSecurityLifecycleSource().fetch(
            code="920176",
            market=MarketCode.BSE,
        )


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
