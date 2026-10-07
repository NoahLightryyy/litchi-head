"""Time-stratified archive retrieval and bounded follow-up evidence searches."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from src.data.models import NewsItem
from src.data.news_archive import ArchiveCoverage, ArchivedArticle, archive
from src.data.news_context import format_news_context


def related(article: ArchivedArticle, code: str, name: str) -> bool:
    body = article.title + " " + article.content
    return bool(
        (name and name in body) or (code and re.search(rf"(?<!\d){re.escape(code)}(?!\d)", body))
    )


def retrieve(code: str, name: str, days: int, end: datetime, term: str = "") -> list[NewsItem]:
    found: dict[str, ArchivedArticle] = {}
    for keyword in dict.fromkeys(value for value in (name, code) if value):
        result = archive.query(days=days, keyword=keyword, secondary=term, page_size=200, end=end)
        for item in result.data:
            if related(item, code, name) and (
                not term or term.casefold() in (item.title + " " + item.content).casefold()
            ):
                found[item.id] = item
    return [
        NewsItem(
            code=code,
            title=item.title,
            date=item.date[:10],
            published_at=datetime.fromisoformat(item.date),
            source=item.source,
            source_id=f"{item.channel}-archive",
            url=item.url,
            content=item.content,
            external_id=item.id,
            association_reason="archive_company_match",
        )
        for item in found.values()
    ]


def research_context(code: str, name: str, end: datetime | None = None) -> tuple[str, list[dict]]:
    end = end or datetime.now(UTC)
    lines = [
        "【分周期新闻资料库】以下是历史背景证据，不是新的预测周期。"
        "资料只反映已采集范围，旧报道不得当作当下事实。每个检索片段最多各取公司名/代码匹配200条。"
    ]
    coverage: list[ArchiveCoverage] = archive.query(days=1, page_size=1, end=end).coverage
    for label, days, offset, limit in (
        ("短期背景：最近7天", 7, 0, 20),
        ("中期背景：最近93天", 93, 0, 30),
        ("长期背景：最近一年", 365, 0, 15),
        ("长期背景：一至两年前", 365, 365, 15),
        ("长期背景：两至三年前", 365, 730, 15),
    ):
        items = retrieve(code, name, days, end - timedelta(days=offset))
        lines.append(label + "\n" + "\n".join(format_news_context(items, limit)))
    for source in coverage:
        lines.append(
            f"{source.source}：入库{source.count}条；时间{source.oldest}至{source.newest}；"
            f"历史状态{source.history_status}；完整覆盖未证明。{source.error or ''}"
        )
    return "\n".join(lines), [item.model_dump() for item in coverage]


def followup_context(code: str, name: str, terms: list[str]) -> str:
    lines = ["【补证检索记录】仅从本地已入库原文检索；未命中不代表事件不存在。"]
    for term in dict.fromkeys(t.strip()[:80] for t in terms[:3] if t.strip()):
        items = retrieve(code, name, 1095, datetime.now(UTC), term)
        lines.append(f"检索词：{term}\n" + "\n".join(format_news_context(items, 20)))
    return "\n".join(lines)
