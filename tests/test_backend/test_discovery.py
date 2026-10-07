from unittest.mock import patch

import pytest

from backend.routers.discovery import SearchHit, search


@pytest.mark.asyncio
async def test_sector_search_is_distinct_from_stock_and_trimmed():
    with patch("backend.routers.discovery.stock_catalog", return_value=[
        SearchHit(code="600001", name="半导体公司", kind="stock")
    ]), patch("backend.routers.discovery.board_catalog", return_value=[
        SearchHit(code="BK001", name="半导体", kind="industry")
    ]):
        result = await search(" 半导体 ")
    assert result.data[0].kind == "industry"
    assert result.total == 2


@pytest.mark.asyncio
async def test_partial_failure_and_no_match_are_distinct():
    with patch("backend.routers.discovery.stock_catalog", side_effect=ValueError), patch(
        "backend.routers.discovery.board_catalog", return_value=[]
    ):
        result = await search("不存在")
    assert not result.data and result.failed_sources == ["股票目录"]
