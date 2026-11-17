from unittest.mock import AsyncMock, patch

import pytest

from backend.routers.discovery import SearchHit, search
from src.data.models import StockInfo
from src.data.providers.stock_catalog import PartialStockCatalogError, StockCatalogSnapshot


@pytest.fixture(autouse=True)
def isolated_etf_catalog():
    with patch("backend.routers.discovery.etf_catalog", new=AsyncMock(return_value=[])):
        yield


@pytest.mark.asyncio
async def test_sector_search_is_distinct_from_stock_and_trimmed():
    with (
        patch(
            "backend.routers.discovery.stock_catalog",
            return_value=[SearchHit(code="600001", name="半导体公司", kind="stock")],
        ),
        patch(
            "backend.routers.discovery.board_catalog",
            return_value=[SearchHit(code="BK001", name="半导体", kind="industry")],
        ),
    ):
        result = await search(" 半导体 ")
    assert result.data[0].kind == "industry"
    assert result.total == 2


@pytest.mark.asyncio
async def test_partial_failure_and_no_match_are_distinct():
    with (
        patch("backend.routers.discovery.stock_catalog", side_effect=ValueError),
        patch("backend.routers.discovery.board_catalog", return_value=[]),
    ):
        result = await search("不存在")
    assert not result.data and result.failed_sources == ["股票目录"]


@pytest.mark.asyncio
async def test_exchange_failure_keeps_stock_match_and_incomplete_flag():
    partial = StockCatalogSnapshot(
        items=[StockInfo(code="002885", name="京泉华")], failed_markets=["沪市"],
    )
    with (
        patch("backend.routers.discovery.stock_catalog",
              side_effect=PartialStockCatalogError(partial)),
        patch("backend.routers.discovery.board_catalog", return_value=[]),
    ):
        result = await search("京泉华")
    assert result.data == [SearchHit(code="002885", name="京泉华", kind="stock")]
    assert result.failed_sources == ["股票目录"]
    assert result.total == 1
