"""Company context from bounded Sina disclosures, independent of trading evidence."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, urlsplit

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)
HOST = "https://vip.stock.finance.sina.com.cn"


class CompanySource(BaseModel):
    id: str
    title: str
    url: str
    published_at: date | None = None
    excerpt: str = Field(min_length=1, max_length=36000)


class CompanyEvidence(BaseModel):
    stock_code: str = Field(pattern=r"^\d{6}$")
    company_name: str
    fetched_at: datetime
    sources: list[CompanySource]
    gaps: list[str]


class CitedInsight(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=400)
    basis: Literal["disclosed", "inference"]
    source_ids: list[str] = Field(min_length=1, max_length=3)


class CompanyInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    niche: CitedInsight
    upstream: CitedInsight
    role: CitedInsight
    downstream: CitedInsight
    highlights: list[CitedInsight] = Field(min_length=1, max_length=4)
    watchpoints: list[CitedInsight] = Field(min_length=1, max_length=4)


class CompanyResearch(BaseModel):
    schema_version: Literal[1] = 1
    stock_code: str = Field(pattern=r"^\d{6}$")
    company_name: str
    generated_at: datetime
    fetched_at: datetime
    model: str
    review_status: Literal["ai_unreviewed"] = "ai_unreviewed"
    purpose: Literal["company_context_only"] = "company_context_only"
    sources: list[CompanySource]
    gaps: list[str]
    interpretation: CompanyInterpretation


def validate_citations(result: CompanyInterpretation, sources: list[CompanySource]) -> None:
    allowed = {source.id for source in sources}
    for item in [result.niche, result.upstream, result.role, result.downstream,
                 *result.highlights, *result.watchpoints]:
        if len(set(item.source_ids)) != len(item.source_ids) or not set(item.source_ids) <= allowed:
            raise ValueError("Unknown or duplicate company evidence citation")


def parse_profile(html: str, code: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    identity = soup.select_one("#stockName")
    table = soup.select_one("#comInfo1")
    if not identity or not re.search(rf"\({code}(?:\.[A-Z]+)?\)", identity.get_text()):
        raise ValueError("Company identity mismatch")
    if not table:
        raise ValueError("Missing company profile")
    fields: dict[str, str] = {}
    for row in table.select("tr"):
        cells = row.select("td")
        for index in range(0, len(cells) - 1, 2):
            fields[cells[index].get_text(strip=True).rstrip("：:")] = cells[index + 1].get_text(
                " ", strip=True,
            )
    name, business = fields.get("公司名称", ""), fields.get("主营业务", "")
    if not name or len(business) < 5:
        raise ValueError("Company business unavailable")
    return name, f"公司名称：{name}\n主营业务：{business}"[:8000]


def report_links(html: str, code: str) -> list[tuple[str, str]]:
    """Only company-bound annual/interim reports; no model-chosen URLs or redirects."""
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, tuple[str, str]] = {}
    for link in soup.select("a[href]"):
        url = urlsplit(str(link["href"]))
        title = link.get_text(" ", strip=True)
        query = parse_qs(url.query)
        ids = query.get("id", [])
        if (url.path != "/corp/view/vCB_AllBulletinDetail.php"
                or query.get("stockid") != [code] or len(ids) != 1 or not ids[0].isdigit()
                or not re.search(r"20\d{2}年(?:半年度|年度)报告", title)
                or any(word in title for word in ("摘要", "取消", "英文"))):
            continue
        found[ids[0]] = (title, f"{HOST}{url.path}?stockid={code}&id={ids[0]}")
    return list(found.values())[:2]


def parse_report(html: str, company: str, title: str, url: str, source_id: str) -> CompanySource:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("#content")
    if not content:
        raise ValueError("Report body missing")
    text = re.sub(r"\s+", " ", content.get_text(" ", strip=True))
    if re.sub(r"\s+", "", company) not in re.sub(r"\s+", "", text[:16000]):
        raise ValueError("Report company mismatch")
    published = re.search(r"公告日期\s*[:：]\s*(\d{4}-\d{2}-\d{2})", soup.get_text(" "))
    if not published:
        raise ValueError("Report date missing")
    report_date = date.fromisoformat(published[1])
    if report_date > datetime.now(UTC).date():
        raise ValueError("Future report")
    # Opening business review and explicitly separated later risk/R&D snippets.
    parts = [text[:24000]]
    for keyword in ("附条件", "重大风险", "核心竞争力", "研发项目"):
        match = text.find(keyword, 24000)
        if match >= 0:
            parts.append("【补充摘录】" + text[max(0, match - 200):match + 1600])
    return CompanySource(id=source_id, title=title, url=url, published_at=report_date,
                         excerpt="\n".join(parts)[:36000])


async def fetch_evidence(code: str) -> CompanyEvidence:
    async with httpx.AsyncClient(timeout=12, follow_redirects=False,
                                 headers={"User-Agent": "Mozilla/5.0"}) as client:
        async def html(url: str) -> str:
            response = await client.get(url)
            response.raise_for_status()
            if len(response.content) > 6_000_000:
                raise ValueError("Oversized disclosure")
            return response.content.decode("gb18030", errors="replace")

        profile_url = f"{HOST}/corp/go.php/vCI_CorpInfo/stockid/{code}.phtml"
        name, profile = parse_profile(await html(profile_url), code)
        sources = [CompanySource(id="profile", title="新浪公司资料（主营业务）",
                                 url=profile_url, excerpt=profile)]
        gaps = ["公司资料未标注更新日期；报告为节选，未覆盖全部公告及最新事件。"]

        async def report(kind: str, source_id: str) -> CompanySource | None:
            try:
                listing = await html(
                    f"{HOST}/corp/go.php/vCB_Bulletin/stockid/{code}/page_type/{kind}.phtml",
                )
                candidates = report_links(listing, code)
                if not candidates:
                    raise ValueError("No report listed")
                title, url = candidates[0]
                return parse_report(await html(url), name, title, url, source_id)
            except Exception:
                logger.warning("Company report unavailable code=%s kind=%s", code, kind,
                               exc_info=True)
                return None

        results = await asyncio.gather(report("ndbg", "annual"), report("zqbg", "interim"))
        for result in results:
            if result:
                sources.append(result)
        if len(sources) < 3:
            gaps.append("部分定期报告未取得，本次仅解读列出的资料。")
        if len(sources) == 1:
            gaps.append("缺少财报正文，无法核验产品优势、经营表现和研发进展。")
        return CompanyEvidence(stock_code=code, company_name=name, fetched_at=datetime.now(UTC),
                               sources=sources, gaps=gaps)


class CompanyResearchStore:
    """Persist the last successful, validated interpretation per stock atomically."""

    def __init__(self, path: Path = Path("data/company_research/results.db")) -> None:
        self.path = path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            with connection:
                connection.execute("CREATE TABLE IF NOT EXISTS company_research "
                                   "(code TEXT PRIMARY KEY, body TEXT NOT NULL, "
                                   "digest TEXT NOT NULL)")
                yield connection
        finally:
            connection.close()

    def save(self, result: CompanyResearch) -> None:
        validate_citations(result.interpretation, result.sources)
        body = result.model_dump_json()
        with self._connect() as connection:
            connection.execute("INSERT OR REPLACE INTO company_research VALUES (?, ?, ?)",
                               (result.stock_code, body, hashlib.sha256(body.encode()).hexdigest()))

    def get(self, code: str) -> CompanyResearch | None:
        with self._connect() as connection:
            row = connection.execute("SELECT body,digest FROM company_research WHERE code=?",
                                     (code,)).fetchone()
        if row is None:
            return None
        if hashlib.sha256(row[0].encode()).hexdigest() != row[1]:
            raise ValueError("Stored company research checksum mismatch")
        result = CompanyResearch.model_validate_json(row[0])
        if result.stock_code != code:
            raise ValueError("Stored company research identity mismatch")
        validate_citations(result.interpretation, result.sources)
        return result
