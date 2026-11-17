"""Keyword retrieval over existing policy snapshots and the continuously collected news archive."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime, timedelta
from typing import Literal
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup
from pydantic import HttpUrl

from backend.async_utils import BoundedSyncRunner
from backend.company_research import HOST, parse_profile
from backend.news_display import NewsDisplay
from backend.news_display import service as company_news_service
from backend.policy_evidence import EvidenceRepository
from backend.related_keywords import extract_keywords
from backend.related_research_contract import (
    RelatedDocument,
    RelatedKeyword,
    RelatedResearchResult,
    RelatedSourceStatus,
    SubjectKind,
)
from src.data.news_archive import NewsArchive, archive

logger = logging.getLogger(__name__)
POLICY = re.compile(
    r"政策|监管(?:新规|规定)|补贴|关税|出口管制|指导意见|行动方案|减税|税收优惠|降准|降息"
    r"|(?:国务院|部委|工信部|发改委|财政部|央行|监管总局).{0,25}"
    r"(?:印发|出台|颁布|下发|实施|部署|支持|推进|推动)"
)
_runner = BoundedSyncRunner(max_workers=2, thread_name_prefix="related-research")
_profile_cache: dict[str, tuple[float, str, str]] = {}
_profile_slots = asyncio.Semaphore(3)


def clean_text(value: str) -> str:
    return re.sub(
        r"\s+", " ", BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    ).strip()


def term_matches(term: str, text: str) -> bool:
    if re.fullmatch(r"[A-Za-z0-9. -]+", term):
        return bool(
            re.search(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", text, re.I)
        )
    return term.casefold() in text.casefold()


def excerpt(text: str, terms: list[str]) -> str:
    positions = [text.casefold().find(term.casefold()) for term in terms]
    start = max(0, min((p for p in positions if p >= 0), default=0) - 70)
    return (
        ("…" if start else "")
        + text[start : start + 500]
        + ("…" if len(text) > start + 500 else "")
    )


def policy_related(text: str, terms: list[str]) -> bool:
    # A long news digest can mention a government notice and an unrelated stock.
    # Require the policy cue near a matched term, not anywhere in the document.
    for sentence in re.split(r"[。！？!?；;\n]|\d+、", text):
        for term in terms:
            for match in re.finditer(re.escape(term), sentence, flags=re.I):
                if POLICY.search(sentence[max(0, match.start() - 90) : match.end() + 90]):
                    return True
    return False


def make_document(
    *,
    identity: str,
    title: str,
    content: str,
    url: str,
    publisher: str,
    stamp: str,
    source: str,
    keywords: list[RelatedKeyword],
    code: str,
    name: str,
    now: datetime,
) -> RelatedDocument | None:
    try:
        parsed = urlsplit(url)
        published = datetime.fromisoformat(stamp)
        if published.tzinfo is None:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", stamp):
                return None
            published = published.replace(tzinfo=UTC)
        if (
            published > now
            or parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            return None
        title, content = clean_text(title), clean_text(content)
        # Some feeds put the entire flash article in title; retain its headline
        # for readability and cross-source dedup, while searching the full body.
        headline = re.match(r"^【([^】]{2,150})】", title)
        if headline:
            content = content or title
            title = headline.group(1)
        if len(title) < 2 or title.lower() in {"nan", "none", "null"}:
            return None
        text = title + " " + content
        hits = [item.term for item in keywords if term_matches(item.term, text)]
        if not hits:
            return None
        direct = term_matches(code, text) or (
            len(name) >= 2 and name != code and term_matches(name, text)
        )
        return RelatedDocument(
            id=identity,
            title=title[:300],
            url=HttpUrl(url),
            publisher=publisher or "来源未标明",
            published_at=stamp,
            excerpt=excerpt(content or title, hits),
            source="policy_archive"
            if source == "policy_archive"
            else "company_news"
            if source == "company_news"
            else "news_archive",
            category="policy"
            if policy_related(title, hits) or policy_related(content, hits)
            else "report",
            relevance="direct" if direct else "topic",
            matched_keywords=hits,
            reason=("直接提及标的名称或代码" if direct else "主题关键词相关")
            + "："
            + "、".join(hits),
        )
    except (ValueError, TypeError):
        return None


def search_news(
    store: NewsArchive,
    keywords: list[RelatedKeyword],
    code: str,
    name: str,
    now: datetime,
) -> list[RelatedDocument]:
    if not keywords:
        return []
    # One bounded OR query; each article keeps the source's date and URL.
    matching = " OR ".join("instr(lower(title || ' ' || content),?)>0" for _ in keywords)
    policy_words = ("政策", "国务院", "工信部", "发改委", "监管新规", "补贴", "关税")
    policy_title = " OR ".join("instr(title,?)>0" for _ in policy_words)
    with closing(store.connect()) as conn:
        conn.set_progress_handler(lambda: int(time.monotonic() >= deadline), 10000)
        deadline = time.monotonic() + 4
        rows = conn.execute(
            f"SELECT * FROM articles WHERE date>=? AND date<=? AND ({matching}) "
            "ORDER BY (instr(title,?)>0 OR instr(title,?)>0) DESC, "
            f"({policy_title}) DESC, date DESC LIMIT 600",
            [
                (now - timedelta(days=365)).isoformat(),
                now.isoformat(),
                *[item.term.casefold() for item in keywords],
                code,
                name or code,
                *policy_words,
            ],
        ).fetchall()
    result = []
    for row in rows:
        item = make_document(
            identity="news:" + row["id"],
            title=row["title"],
            content=row["content"],
            url=row["url"],
            publisher=row["source"],
            stamp=row["date"],
            source="news_archive",
            keywords=keywords,
            code=code,
            name=name,
            now=now,
        )
        if item:
            result.append(item)
    return result


def search_policies(
    repository: EvidenceRepository,
    keywords: list[RelatedKeyword],
    code: str,
    name: str,
    now: datetime,
) -> list[RelatedDocument]:
    packages = json.loads((repository.root / "packages.json").read_text(encoding="utf-8"))
    found: dict[str, RelatedDocument] = {}
    for package_id in packages:
        package = repository.get(package_id)
        for evidence in package.evidence:
            # Reuse public policy/reporting documents, never another company's holdings or claims.
            if evidence.role not in {"official_repost", "reporting"}:
                continue
            item = make_document(
                identity="policy:" + evidence.canonical_document_id,
                title=evidence.title,
                content=evidence.summary,
                url=str(evidence.url),
                publisher=evidence.publisher,
                stamp=evidence.published_date.isoformat(),
                source="policy_archive",
                keywords=keywords,
                code=code,
                name=name,
                now=now,
            )
            if item:
                found[item.id] = item
    return list(found.values())


def rank_documents(documents: list[RelatedDocument]) -> list[RelatedDocument]:
    def score(item: RelatedDocument) -> tuple[int, int, int, int, str, int]:
        title_hits = sum(term_matches(term, item.title) for term in item.matched_keywords)
        return (
            int(title_hits > 0),
            int(item.relevance == "direct"),
            int(item.category == "policy"),
            int(item.source == "policy_archive"),
            item.published_at,
            title_hits,
        )

    found: list[RelatedDocument] = []
    titles: set[str] = set()
    urls: set[str] = set()
    for item in sorted(documents, key=score, reverse=True):
        normalized = re.sub(r"[\W_]", "", item.title).casefold()
        url = str(item.url).split("#")[0]
        if normalized in titles or url in urls:
            continue
        titles.add(normalized)
        urls.add(url)
        found.append(item)
    # Reserve a small policy section when direct market reports dominate the feed.
    policies = [item for item in found if item.category == "policy"][:4]
    selected = policies + [item for item in found if item not in policies][: 12 - len(policies)]
    return sorted(selected, key=score, reverse=True)


async def company_context(code: str) -> tuple[str, str]:
    cached = _profile_cache.get(code)
    if cached and time.monotonic() - cached[0] < 3600:
        return cached[1], cached[2]
    async with (
        _profile_slots,
        httpx.AsyncClient(
            timeout=4, follow_redirects=False, headers={"User-Agent": "Mozilla/5.0"}
        ) as client,
    ):
        response = await client.get(f"{HOST}/corp/go.php/vCI_CorpInfo/stockid/{code}.phtml")
        response.raise_for_status()
        if len(response.content) > 2_000_000:
            raise ValueError("Oversized profile")
        result = parse_profile(response.content.decode("gb18030", errors="replace"), code)
        # Bounded cache; no growth with unbounded stock IDs.
        if len(_profile_cache) >= 256:
            _profile_cache.pop(next(iter(_profile_cache)))
        _profile_cache[code] = (time.monotonic(), *result)
        return result


def retrieve(
    kind: SubjectKind,
    code: str,
    name: str,
    business: str,
    query: str,
    profile_status: RelatedSourceStatus,
    *,
    store: NewsArchive = archive,
    repository: EvidenceRepository | None = None,
    now: datetime | None = None,
) -> RelatedResearchResult:
    now = now or datetime.now(UTC)
    keywords = extract_keywords(kind, code, name, business, query)
    documents: list[RelatedDocument] = []
    sources = [profile_status]
    readers: tuple[
        tuple[Literal["news_archive", "policy_archive"], Callable[[], list[RelatedDocument]]], ...
    ] = (
        ("news_archive", lambda: search_news(store, keywords, code, name, now)),
        (
            "policy_archive",
            lambda: search_policies(repository or EvidenceRepository(), keywords, code, name, now),
        ),
    )
    for source, read in readers:
        try:
            documents.extend(read())
            sources.append(RelatedSourceStatus(source=source, status="ok"))
        except Exception:
            logger.exception("Related research source failed: %s", source)
            sources.append(
                RelatedSourceStatus(
                    source=source,
                    status="unavailable",
                    message="资料库暂时无法读取，可重试；其他来源仍可展示。",
                )
            )
    data = rank_documents(documents)
    failed = any(item.status == "unavailable" for item in sources)
    all_failed = all(
        item.status == "unavailable" for item in sources if item.source != "company_profile"
    )
    status = (
        ("partial" if failed else "ready") if data else ("unavailable" if all_failed else "empty")
    )
    return RelatedResearchResult(
        subject_kind=kind,
        subject_id=code,
        subject_name=name,
        query=query,
        status=status,
        keywords=keywords,
        data=data,
        sources=sources,
        searched_at=now,
        limitations=[
            "按名称、主营业务和主题词匹配，相关性不等于政策受益结论。",
            "资讯范围为近365天已入库报道，另含已归档政策；不代表全网或最新政策全集。",
        ],
    )


def merge_company_news(
    result: RelatedResearchResult, display: NewsDisplay
) -> RelatedResearchResult:
    if display.symbol != result.subject_id:
        raise ValueError("Company news identity mismatch")
    additions: list[RelatedDocument] = []
    for item in display.items:
        if not item.published_at or not item.provenance:
            continue
        origin = item.provenance[0]
        document = make_document(
            identity="company:" + item.id,
            title=item.title,
            content="",
            url=origin.url,
            publisher=origin.publisher,
            stamp=item.published_at,
            source="company_news",
            keywords=result.keywords,
            code=result.subject_id,
            name=result.subject_name,
            now=result.searched_at,
        )
        if document:
            document.reason += "；公司新闻查询，仅标题，未读取全文"
            additions.append(document)
    sources = [
        *result.sources,
        RelatedSourceStatus(
            source="company_news",
            status="unavailable" if display.status in {"failed", "partial"} else "ok",
            message="已复用近90日公司新闻；仅代表已取得的标题范围。"
            if display.items
            else "公司新闻暂无可用材料。",
        ),
    ]
    data = rank_documents([*result.data, *additions])
    failed = any(s.status == "unavailable" for s in sources)
    all_failed = all(s.status == "unavailable" for s in sources if s.source != "company_profile")
    return result.model_copy(
        update={
            "data": data,
            "sources": sources,
            "status": ("partial" if failed else "ready")
            if data
            else ("unavailable" if all_failed else "empty"),
            "limitations": [
                *result.limitations,
                "另补充近90日公司新闻和公告标题，未取得全文；标题不能证明订单或利润已兑现。",
            ],
        }
    )


async def related_research(
    kind: SubjectKind, code: str, name: str, query: str
) -> RelatedResearchResult:
    async def archive_result() -> RelatedResearchResult:
        business = ""
        profile = RelatedSourceStatus(source="company_profile", status="not_requested")
        if kind == "stock" and not query:
            try:
                _, business = await asyncio.wait_for(company_context(code), timeout=4.5)
                profile = RelatedSourceStatus(source="company_profile", status="ok")
            except Exception:
                logger.warning("Related research company profile unavailable: %s", code)
                profile = RelatedSourceStatus(
                    source="company_profile",
                    status="unavailable",
                    message="主营资料暂未取得，已按名称和代码检索。",
                )
        return await asyncio.wait_for(
            _runner.run(retrieve, kind, code, name, business, query, profile), timeout=8
        )

    if kind != "stock":
        return await archive_result()
    result, news = await asyncio.gather(
        archive_result(), company_news_service.get(code, 90), return_exceptions=True
    )
    if isinstance(result, asyncio.CancelledError):
        raise result
    if isinstance(result, BaseException):
        logger.warning("Related archive retrieval failed; retaining company news: %s", code)
        result = RelatedResearchResult(
            subject_kind=kind,
            subject_id=code,
            subject_name=name,
            query=query,
            status="unavailable",
            keywords=extract_keywords(kind, code, name, "", query),
            data=[],
            sources=[
                RelatedSourceStatus(source=source, status="unavailable")
                for source in ("news_archive", "policy_archive")
            ],
            searched_at=datetime.now(UTC),
            limitations=["归档资料暂未取得，先查看已取得的公司新闻。"],
        )
    try:
        if isinstance(news, BaseException):
            raise news
        return merge_company_news(result, news)
    except Exception:
        logger.exception("Company news reuse failed: %s", code)
        return result.model_copy(
            update={
                "status": "partial" if result.data else result.status,
                "sources": [
                    *result.sources,
                    RelatedSourceStatus(
                        source="company_news",
                        status="unavailable",
                        message="公司新闻暂未取得，保留其他资料。",
                    ),
                ],
            }
        )
