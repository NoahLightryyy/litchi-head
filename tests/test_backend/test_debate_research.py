"""Active supplementation retains raw provenance and isolated failures."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from backend.company_research import CompanyEvidence, CompanySource
from backend.debate_research import collect_research_context
from backend.technical_research import TechnicalResearch
from src.data.fundamental_research import FundamentalResearch


@pytest.mark.asyncio
async def test_company_facts_are_fetched_even_when_news_fails() -> None:
    evidence = CompanyEvidence(stock_code="300893", company_name="测试公司",
        fetched_at=datetime.now(UTC), gaps=[], sources=[CompanySource(
            id="profile", title="主营资料", url="https://example.com/source",
            excerpt="安全系统研发生产",)])
    with (
        patch("backend.debate_research.fetch_evidence", AsyncMock(return_value=evidence)) as fetch,
        patch("backend.debate_research.collect_display", AsyncMock(side_effect=ValueError("bad"))),
        patch("backend.debate_research.get_technical_research", return_value=TechnicalResearch(
            stock_code="300893", status="unavailable", fetched_at=datetime.now(UTC),
        )),
        patch("backend.debate_research.get_fundamental_research", return_value=FundamentalResearch(
            stock_code="300893", status="unavailable", warnings=["利润表未取得"],
        )),
    ):
        result = await collect_research_context("300893")
    fetch.assert_awaited_once_with("300893")
    assert "安全系统研发生产" in result and "https://example.com/source" in result
    assert "已尝试补证但未取得有效资料" in result and "利润表未取得" in result
    assert "不改变交易准入" in result
    assert "双源历史日线及MA/RSI/MACD/KDJ" in result and "RSI14" in result


@pytest.mark.asyncio
async def test_foreign_company_evidence_is_not_injected() -> None:
    foreign = FundamentalResearch(stock_code="000001", status="unavailable")
    with (
        patch("backend.debate_research.fetch_evidence", AsyncMock(return_value=foreign)),
        patch("backend.debate_research.collect_display", AsyncMock(return_value=foreign)),
        patch("backend.debate_research.get_fundamental_research", return_value=foreign),
        patch("backend.debate_research.get_technical_research", return_value=foreign),
    ):
        result = await collect_research_context("300893")
    assert "000001" not in result
    assert result.count("已尝试补证但未取得有效资料") == 4
