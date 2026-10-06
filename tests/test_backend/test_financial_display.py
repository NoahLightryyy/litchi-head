from datetime import date

from backend.financial_display import enrich
from src.data.fundamental_research import Statement
from src.data.models import FinancialMetrics


def test_same_period_margin_missing_zero_and_preservation():
    item = FinancialMetrics(stock_code="001246", report_date="2026-06-30")
    statement = Statement(
        kind="lrb",
        report_date=date(2026, 6, 30),
        published_at=None,
        source_url="https://quotes.sina.cn/",
        amounts={"BIZINCO": 100, "BIZCOST": 75},
    )
    assert enrich([item], [statement])[0].gross_margin == 25
    statement.amounts["BIZCOST"] = 100
    assert enrich([item], [statement])[0].gross_margin == 0
    statement.amounts["BIZCOST"] = None
    assert enrich([item], [statement])[0].gross_margin is None
    statement.report_date = date(2026, 3, 31)
    assert enrich([item], [statement])[0].gross_margin is None
    item.gross_margin = 12
    assert enrich([item], [statement])[0].gross_margin == 12
