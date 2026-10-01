"""Bounded, provenance-preserving consolidated financial research (Sina).

Independent of legacy indicator tables: absent amounts never become zero.
No inference of investment ratings or market-value scope from financials.
"""

from __future__ import annotations

import logging
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from threading import Lock
from typing import Any, Literal

import requests
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
URL = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"
FIELDS = {"BIZINCO", "BIZCOST", "PARENETP", "TOTASSET", "TOTLIAB", "PARESHARRIGH", "MANANETR"}


class Statement(BaseModel):
    kind: Literal["lrb", "fzb", "llb"]
    report_date: date
    published_at: date | None
    source_url: str
    currency: Literal["CNY"] = "CNY"
    scope: Literal["合并期末"] = "合并期末"
    amounts: dict[str, float | None]


class ResearchMetric(BaseModel):
    value: float | None = Field(default=None, allow_inf_nan=False)
    unit: str
    basis: str
    reason: str | None = None


class FundamentalResearch(BaseModel):
    schema_version: Literal[1] = 1
    stock_code: str
    status: Literal["available", "partial", "stale", "unavailable"]
    report_date: date | None = None
    fetched_at: datetime | None = None
    source: Literal["sina_consolidated_statements"] = "sina_consolidated_statements"
    verification: Literal["single_source"] = "single_source"
    statements: list[Statement] = Field(default_factory=list)
    metrics: dict[str, ResearchMetric] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    retryable: bool = False


def parse_statements(
    payload: dict[str, Any], kind: Literal["lrb", "fzb", "llb"], source_url: str
) -> list[Statement]:
    """Reject ambiguous scope/duplicate facts; retain missing fields as null."""
    reports = payload["result"]["data"]["report_list"]
    result: list[Statement] = []
    today = datetime.now(timezone(timedelta(hours=8))).date()
    for raw_period, raw in reports.items():
        if raw.get("rType") != "合并期末" or raw.get("rCurrency") != "CNY":
            continue
        period = datetime.strptime(raw_period, "%Y%m%d").date()
        if raw_period[4:] not in {"0331", "0630", "0930", "1231"}:
            raise ValueError("Not a quarterly/yearly reporting period")
        published = raw.get("publish_date")
        published_at = datetime.strptime(published, "%Y%m%d").date() if published else None
        if period > today or (published_at and not period <= published_at <= today):
            raise ValueError("Invalid financial publication/period date")
        amounts: dict[str, float | None] = {}
        for item in raw["data"]:
            key = item["item_field"]
            if key not in FIELDS:
                continue
            if key in amounts:
                raise ValueError("Duplicate financial fact")
            value = item.get("item_value")
            number = None if value in (None, "", "--", "-") else float(value)
            if number is not None and not math.isfinite(number):
                raise ValueError("Nonfinite financial fact")
            amounts[key] = number
        result.append(
            Statement(
                kind=kind,
                report_date=period,
                published_at=published_at,
                source_url=source_url,
                amounts=amounts,
            )
        )
    return sorted(result, key=lambda row: row.report_date, reverse=True)


def _fetch(code: str, kind: Literal["lrb", "fzb", "llb"]) -> list[Statement]:
    prefix = (
        "bj"
        if code.startswith(("4", "8", "92"))
        else "sh"
        if code.startswith(("5", "6", "9"))
        else "sz"
    )
    response = requests.get(
        URL,
        params={"paperCode": prefix + code, "source": kind, "type": "0", "page": "1", "num": "16"},
        timeout=(3, 8),
    )
    response.raise_for_status()
    return parse_statements(response.json(), kind, response.url)


def build_research(
    code: str, tables: dict[str, list[Statement]], warnings: list[str]
) -> FundamentalResearch:
    income = tables.get("lrb", [])
    if not income:
        return FundamentalResearch(
            stock_code=code,
            status="unavailable",
            retryable=True,
            warnings=[*warnings, "未取得合并利润表，请重试；不使用旧指标表补零。"],
        )
    latest = max(income, key=lambda row: row.report_date)
    period = latest.report_date
    used: dict[tuple[str, date], Statement] = {}

    def fact(kind: str, key: str, at: date = period) -> float | None:
        row = next((item for item in tables.get(kind, []) if item.report_date == at), None)
        if row is None:
            return None
        used[(kind, at)] = row
        return row.amounts.get(key)

    def growth(key: str) -> float | None:
        current = fact("lrb", key)
        prior = fact("lrb", key, period.replace(year=period.year - 1))
        return (
            (current - prior) / abs(prior) * 100
            if current is not None and prior is not None and prior != 0
            else None
        )

    def ttm(key: str) -> float | None:
        current = fact("lrb", key)
        if period.month == 12 and period.day == 31:
            return current
        annual = fact("lrb", key, date(period.year - 1, 12, 31))
        prior = fact("lrb", key, period.replace(year=period.year - 1))
        if current is None or annual is None or prior is None:
            return None
        return current + annual - prior

    def ratio(a: float | None, b: float | None) -> float | None:
        return a / b * 100 if a is not None and b is not None and b > 0 else None

    revenue, cost = fact("lrb", "BIZINCO"), fact("lrb", "BIZCOST")
    parent, equity = fact("lrb", "PARENETP"), fact("fzb", "PARESHARRIGH")
    values = {
        "revenue": (revenue, "元", "合并利润表营业收入；本年累计，非主营业务利润"),
        "gross_margin": (
            ratio(revenue - cost if revenue is not None and cost is not None else None, revenue),
            "%",
            "(营业收入−营业成本)/营业收入；非营业总成本",
        ),
        "parent_profit": (parent, "元", "归属于母公司所有者的净利润；本年累计"),
        "revenue_growth": (growth("BIZINCO"), "%", "(本期累计营业收入−上年同期)/|上年同期|"),
        "parent_profit_growth": (
            growth("PARENETP"),
            "%",
            "归母净利润同比，以上年同期绝对值为分母；非合并净利润同比",
        ),
        "return_on_ending_equity": (
            ratio(parent, equity),
            "%",
            "累计归母净利润/期末归母权益；非加权平均ROE，未年化",
        ),
        "operating_cash_flow": (
            fact("llb", "MANANETR"),
            "元",
            "经营活动产生的现金流量净额；本年累计，非每股现金流",
        ),
        "debt_ratio": (
            ratio(fact("fzb", "TOTLIAB"), fact("fzb", "TOTASSET")),
            "%",
            "同报告期合并负债合计/资产总计",
        ),
        "revenue_ttm": (ttm("BIZINCO"), "元", "本期累计+上年全年−上年同期；年报直接使用全年"),
        "parent_profit_ttm": (
            ttm("PARENETP"),
            "元",
            "归母净利润：本期累计+上年全年−上年同期；年报直接使用全年",
        ),
    }
    metrics = {
        key: ResearchMetric(
            value=value,
            unit=unit,
            basis=basis,
            reason="缺少同口径报表字段，或分母不适用" if value is None else None,
        )
        for key, (value, unit, basis) in values.items()
    }
    for key, basis in {
        "pe": "总市值/归母净利润TTM；亏损不显示PE",
        "pb": "总市值/期末归母权益；非正权益不显示PB",
        "ps": "总市值/营业收入TTM",
    }.items():
        metrics[key] = ResearchMetric(
            unit="倍", basis=basis, reason="缺少可核验时点及股本范围的总市值，暂不计算"
        )
    return FundamentalResearch(
        stock_code=code,
        status="partial",
        report_date=period,
        fetched_at=datetime.now(timezone.utc),
        statements=list(used.values()),
        metrics=metrics,
        warnings=[*warnings, "新浪合并报表单源；不同报告期及后续重述可能影响可比性。"],
        retryable=bool(warnings),
    )


class _Entry:
    def __init__(self) -> None:
        self.lock = Lock()
        self.value: FundamentalResearch | None = None
        self.expires = 0.0


@lru_cache(maxsize=256)
def _entry(code: str) -> _Entry:
    return _Entry()


def get_fundamental_research(code: str) -> FundamentalResearch:
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError("Invalid stock code")
    entry = _entry(code)
    with entry.lock:
        if entry.value is not None and time.monotonic() < entry.expires:
            return entry.value.model_copy(deep=True)
        tables: dict[str, list[Statement]] = {}
        warnings: list[str] = []
        with ThreadPoolExecutor(max_workers=3) as pool:
            pending = {kind: pool.submit(_fetch, code, kind) for kind in ("lrb", "fzb", "llb")}
            for kind, future in pending.items():
                try:
                    tables[kind] = future.result()
                    if not tables[kind]:
                        logger.warning("No consolidated CNY statements: %s %s", code, kind)
                        warnings.append(f"{kind}未返回合并人民币报表")
                except Exception:
                    logger.exception(
                        "Financial statement retrieval failed: code=%s kind=%s", code, kind
                    )
                    warnings.append(f"{kind}报表暂未取得，可手动重试")
        try:
            result = build_research(code, tables, warnings)
        except (ValueError, ArithmeticError):
            logger.exception("Invalid financial calculation: code=%s", code)
            result = FundamentalResearch(
                stock_code=code,
                status="unavailable",
                retryable=True,
                warnings=[*warnings, "报表计算未通过校验，请重试"],
            )
        if result.status == "unavailable" and entry.value is not None:
            old = entry.value
            if old.fetched_at and datetime.now(timezone.utc) - old.fetched_at < timedelta(hours=24):
                return old.model_copy(
                    update={
                        "status": "stale",
                        "retryable": True,
                        "warnings": [*result.warnings, "显示最近成功结果，采集时间未更新。"],
                    },
                    deep=True,
                )
        if result.status != "unavailable":
            entry.value = result.model_copy(deep=True)
            entry.expires = time.monotonic() + (60 if warnings else 900)
        return result
