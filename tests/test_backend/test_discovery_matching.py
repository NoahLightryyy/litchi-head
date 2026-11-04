"""ETF names should be searchable without memorising the provider's word order."""

from unittest.mock import AsyncMock, patch

import pytest

from backend.routers.discovery import SearchHit, SearchResult, search

ETF = SearchHit(code="560780", name="半导体设备ETF广发", kind="etf")
OTHER_MANAGER = SearchHit(code="561980", name="半导体设备ETF招商", kind="etf")
OTHER_TOPIC = SearchHit(code="159000", name="新能源ETF广发", kind="etf")


async def lookup(query: str, *, stocks_fail: bool = False) -> SearchResult:
    with (
        patch(
            "backend.routers.discovery.stock_catalog",
            side_effect=ValueError if stocks_fail else None,
            return_value=[SearchHit(code="000776", name="广发证券", kind="stock")],
        ),
        patch(
            "backend.routers.discovery.board_catalog",
            return_value=[SearchHit(code="BK1036", name="半导体", kind="industry")],
        ),
        patch(
            "backend.routers.discovery.etf_catalog",
            new=AsyncMock(return_value=[ETF, OTHER_MANAGER, OTHER_TOPIC]),
        ),
    ):
        return await search(query)


@pytest.mark.parametrize(
    "query",
    [
        "半导体广发",
        "广发半导体",
        "半导体 广发",
        "广发 半导体 ETF",
        "半导体ETF广发",
        "半导体广发基金的ETF",
        "广发基金的半导体ETF",
        "半导体设备 广发",
        "半导体，广发",
        "广发/半导体",
        "半导体ｅｔｆ广发",
        "560780 广发基金",
        "５６０７８０",
    ],
)
@pytest.mark.asyncio
async def test_etf_theme_manager_and_category_are_order_independent(query: str) -> None:
    result = await lookup(query)
    assert result.data == [ETF]
    assert result.total == 1
    assert not result.failed_sources


@pytest.mark.parametrize(
    "query",
    ["半导体华泰", "半导体 广发 不存在", "半广导发体", "广发广发半导体", "半导体 广发 000776"],
)
@pytest.mark.asyncio
async def test_all_meaningful_terms_must_match_same_identity_not_scattered_characters(
    query: str,
) -> None:
    assert (await lookup(query)).data == []


@pytest.mark.parametrize("query", ["ETF", "基金", "基金的ETF"])
@pytest.mark.asyncio
async def test_category_only_query_does_not_return_stocks_or_boards(query: str) -> None:
    result = await lookup(query)
    assert len(result.data) == 3
    assert all(hit.kind == "etf" for hit in result.data)


@pytest.mark.asyncio
async def test_exact_names_codes_partial_codes_and_failure_flags_preserved() -> None:
    assert (await lookup("560780")).data == [ETF]
    assert (await lookup(ETF.name)).data == [ETF]
    assert (await lookup("56078")).data == [ETF]
    assert (await lookup("广发证券")).data[0].code == "000776"
    assert (await lookup("半导体")).data[0].kind == "industry"
    result = await lookup("半导体广发", stocks_fail=True)
    assert result.data == [ETF]
    assert result.failed_sources == ["股票目录"]


@pytest.mark.asyncio
async def test_search_response_limit_and_dedup_remain_stable() -> None:
    hits = [SearchHit(code=str(510000 + i), name=f"主题ETF广发{i}", kind="etf") for i in range(105)]
    with (
        patch("backend.routers.discovery.stock_catalog", return_value=[]),
        patch("backend.routers.discovery.board_catalog", return_value=[]),
        patch("backend.routers.discovery.etf_catalog", new=AsyncMock(return_value=hits + hits)),
    ):
        result = await search("广发主题")
    assert result.total == 105
    assert len(result.data) == 100
    assert result.data == hits[:100]
