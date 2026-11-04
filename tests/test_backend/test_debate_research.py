"""Active supplementation retains raw provenance and isolated failures."""
from datetime import UTC, datetime
from threading import get_ident
from unittest.mock import AsyncMock, Mock, patch

import pytest

from backend import debate_research
from backend.company_research import CompanyEvidence, CompanySource
from backend.debate_research import collect_research_context
from backend.technical_research import TechnicalResearch
from src.data.fundamental_research import FundamentalResearch


@pytest.fixture(autouse=True)
def saved_interpretation(monkeypatch):
    read = Mock(return_value="")
    monkeypatch.setattr(debate_research, "format_saved_interpretation", read)
    return read


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
    assert "可用历史日线及MA/RSI/MACD/KDJ" in result and "RSI14" in result


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


@pytest.mark.parametrize("saved_state", ["present", "missing", "failed"])
async def test_saved_interpretation_is_optional_read_only_default_query_context(
    saved_interpretation, saved_state, caplog
) -> None:
    event_thread = get_ident()
    read_threads = []
    saved_text = (
        "【已保存AI解读，非原始事实】版本test-1，生成于2026-10-26；"
        "来源https://example.com/policy，报道日期2026-10-20。"
    )

    def read(*args):
        read_threads.append(get_ident())
        if saved_state == "failed":
            raise ValueError("private corrupt record")
        return saved_text if saved_state == "present" else ""

    saved_interpretation.side_effect = read
    evidence = CompanyEvidence(
        stock_code="300893", company_name="测试公司", fetched_at=datetime.now(UTC), gaps=[],
        sources=[CompanySource(id="profile", title="主营资料", url="https://example.com/source",
                               excerpt="安全系统研发生产")],
    )
    with (
        patch("backend.debate_research.fetch_evidence", AsyncMock(return_value=evidence)),
        patch("backend.debate_research.collect_display", AsyncMock(side_effect=OSError("offline"))),
        patch("backend.debate_research.get_technical_research", return_value=TechnicalResearch(
            stock_code="300893", status="unavailable", fetched_at=datetime.now(UTC),
        )),
        patch("backend.debate_research.get_fundamental_research", return_value=FundamentalResearch(
            stock_code="300893", status="unavailable",
        )),
        patch("src.utils.llm.llm_service.invoke_structured", new_callable=AsyncMock) as generate,
    ):
        result = await collect_research_context("300893")

    saved_interpretation.assert_called_once_with("stock", "300893", "")
    assert len(read_threads) == 1 and read_threads[0] != event_thread
    generate.assert_not_called()
    assert "安全系统研发生产" in result and "https://example.com/source" in result
    assert "不改变交易准入" in result
    assert (saved_text in result) == (saved_state == "present")
    assert ("已保存的政策与新闻解读】读取失败" in result) == (saved_state == "failed")
    assert "private corrupt record" not in result
    if saved_state == "failed":
        assert "Saved related interpretation read failed: kind=stock code=300893" in caplog.text
