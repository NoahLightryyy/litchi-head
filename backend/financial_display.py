"""Display-only, same-period gross margin enrichment; never changes trading inputs."""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from threading import Lock

from pydantic import BaseModel

from src.data.fundamental_research import Statement, _fetch
from src.data.models import FinancialMetrics

logger = logging.getLogger(__name__)


class MarginEvidence(BaseModel):
    source_url: str | None = None
    report_date: str
    revenue: float | None = None
    cost: float | None = None
    reason: str


class DisplayFinancial(FinancialMetrics):
    gross_margin_evidence: MarginEvidence | None = None


class FinancialResponse(BaseModel):
    data: list[DisplayFinancial]
    meta: dict[str, bool | int]


class Entry:
    def __init__(self) -> None:
        self.lock = Lock()
        self.expires = 0.0
        self.rows: list[Statement] = []


@lru_cache(maxsize=256)
def _entry(code: str) -> Entry:
    return Entry()


def income_statements(code: str) -> list[Statement]:
    entry = _entry(code)
    with entry.lock:
        if time.monotonic() >= entry.expires:
            try:
                entry.rows = _fetch(code, "lrb")
                entry.expires = time.monotonic() + 900
            except Exception:
                logger.exception("Gross margin statement unavailable: %s", code)
                entry.rows = []
                entry.expires = time.monotonic() + 30
        return entry.rows


def enrich(items: list[FinancialMetrics], statements: list[Statement]) -> list[DisplayFinancial]:
    result: list[DisplayFinancial] = []
    for item in items:
        row = DisplayFinancial(**item.model_dump())
        if row.gross_margin is None:
            matches = [
                s
                for s in statements
                if s.kind == "lrb" and s.report_date.isoformat() == item.report_date
            ]
            statement = matches[0] if len(matches) == 1 else None
            revenue = statement.amounts.get("BIZINCO") if statement else None
            cost = statement.amounts.get("BIZCOST") if statement else None
            valid = revenue is not None and revenue > 0 and cost is not None and cost >= 0
            if valid:
                assert revenue is not None and cost is not None
                row.gross_margin = (revenue - cost) / revenue * 100
            row.gross_margin_evidence = MarginEvidence(
                report_date=item.report_date,
                source_url=statement.source_url if statement else None,
                revenue=revenue,
                cost=cost,
                reason="新浪合并人民币利润表：按同报告期营业收入与营业成本计算，单源，未交叉验证。"
                if valid
                else "原指标源未提供毛利率；同期合并利润表的营业收入或营业成本"
                "缺失或不适用，暂不能计算。",
            )
        result.append(row)
    return result
