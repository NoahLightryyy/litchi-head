"""东方财富个股搜索与新浪财经快讯的统一新闻证据适配器。"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import math
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from src.data.evidence import (
    EvidenceCapability,
    EvidenceRequest,
    SourceDescriptor,
    SourceResult,
    SourceStatus,
)
from src.data.models import NewsItem

logger = logging.getLogger(__name__)

SHANGHAI = ZoneInfo("Asia/Shanghai")
NEWS_TIMEOUT_SECONDS = 10.0
EASTMONEY_PAGE_SIZE = 50
SINA_PAGE_SIZE = 100
MAX_NEWS_PAGES = 20
EASTMONEY_SEARCH_URL = "https://search-api-web.eastmoney.com/search/jsonp"
SINA_FEED_URL = "https://zhibo.sina.com.cn/api/zhibo/feed"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)


class EastmoneyNewsFetcher(Protocol):
    def __call__(
        self,
        *,
        keyword: str,
        page_index: int,
        page_size: int,
    ) -> Mapping[str, Any]:
        """查询一页东方财富个股搜索结果。"""
        ...


class SinaNewsFetcher(Protocol):
    def __call__(
        self,
        *,
        page: int,
        page_size: int,
    ) -> Mapping[str, Any]:
        """查询一页新浪财经快讯。"""
        ...


class _UpstreamRequestError(RuntimeError):
    """区分网络/调用失败与响应格式损坏。"""


def _mapping(value: object, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} 必须是 JSON 对象")
    return value


def _list(value: object, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{context} 必须是数组")
    return value


def _nonnegative_int(value: object, context: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{context} 必须是非负整数")
    try:
        result = int(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} 必须是非负整数") from exc
    if result < 0:
        raise ValueError(f"{context} 必须是非负整数")
    return result


def _aware_shanghai(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=SHANGHAI)
    return value.astimezone(SHANGHAI)


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return _aware_shanghai(value)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=UTC).astimezone(SHANGHAI)

    text = str(value).strip()
    if not text:
        raise ValueError("发布时间为空")
    if text.isdigit():
        return datetime.fromtimestamp(int(text), tz=UTC).astimezone(SHANGHAI)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return _aware_shanghai(parsed)


def _within_window(published_at: datetime, request: EvidenceRequest) -> bool:
    if request.start_at is not None:
        if published_at < _aware_shanghai(request.start_at):
            return False
    if request.end_at is not None:
        if published_at > _aware_shanghai(request.end_at):
            return False
    return True


def _clean_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _association_reason(
    text: str,
    *,
    stock_code: str,
    stock_name: str,
) -> str | None:
    if stock_name and stock_name in text:
        return "stock_name"
    if stock_code and stock_code in text:
        return "stock_code"
    return None


def _content_hash(
    *,
    title: str,
    published_at: datetime,
    publisher: str,
    url: str,
    raw_text: str,
) -> str:
    canonical = "\n".join(
        [
            title.strip(),
            published_at.isoformat(),
            publisher.strip(),
            url.strip(),
            raw_text.strip(),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _news_item(
    *,
    external_id: str,
    request: EvidenceRequest,
    title: str,
    raw_text: str,
    published_at: datetime,
    source_id: str,
    source_name: str,
    publisher: str,
    url: str,
    association_reason: str,
) -> NewsItem:
    return NewsItem(
        external_id=external_id,
        code=request.stock_code,
        title=title,
        date=published_at.date().isoformat(),
        published_at=published_at,
        content="",
        source=source_name,
        source_id=source_id,
        publisher=publisher,
        url=url,
        association_reason=association_reason,
        content_hash=_content_hash(
            title=title,
            published_at=published_at,
            publisher=publisher,
            url=url,
            raw_text=raw_text,
        ),
    )


def _default_eastmoney_fetcher(
    *,
    keyword: str,
    page_index: int,
    page_size: int,
) -> Mapping[str, Any]:
    import httpx

    callback = "jQuery3510000000000000000_0000000000000"
    query = {
        "uid": "",
        "keyword": keyword,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {
            "cmsArticleWebOld": {
                "searchScope": "default",
                "sort": "default",
                "pageIndex": page_index,
                "pageSize": page_size,
                "preTag": "",
                "postTag": "",
            }
        },
    }
    response = httpx.get(
        EASTMONEY_SEARCH_URL,
        params={
            "cb": callback,
            "param": json.dumps(query, ensure_ascii=False, separators=(",", ":")),
            "_": "0",
        },
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://so.eastmoney.com/",
        },
        timeout=NEWS_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    match = re.fullmatch(r".*?\((.*)\)\s*", response.text, flags=re.DOTALL)
    if match is None:
        raise ValueError("东方财富响应不是有效 JSONP")
    payload = json.loads(match.group(1))
    return _mapping(payload, "东方财富响应")


def _default_sina_fetcher(*, page: int, page_size: int) -> Mapping[str, Any]:
    import httpx

    response = httpx.get(
        SINA_FEED_URL,
        params={
            "page": str(page),
            "page_size": str(page_size),
            "zhibo_id": "152",
            "tag_id": "0",
            "dire": "f",
            "dpc": "1",
            "pagesize": str(page_size),
            "type": "1",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=NEWS_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    return _mapping(response.json(), "新浪响应")


def _failed_result(
    *,
    source_id: str,
    upstream_id: str,
    error_code: str,
    exc: Exception,
) -> SourceResult[NewsItem]:
    message = str(exc).strip() or exc.__class__.__name__
    return SourceResult[NewsItem](
        source_id=source_id,
        upstream_id=upstream_id,
        capability=EvidenceCapability.NEWS,
        status=SourceStatus.FAILED,
        error_code=error_code,
        error_message=message,
    )


class EastmoneyNewsSource:
    """东方财富个股搜索直连适配器。"""

    descriptor = SourceDescriptor(
        source_id="eastmoney-stock-search",
        upstream_id="eastmoney",
        display_name="东方财富个股搜索",
        capabilities={EvidenceCapability.NEWS},
    )

    def __init__(
        self,
        *,
        fetcher: EastmoneyNewsFetcher = _default_eastmoney_fetcher,
        max_pages: int = MAX_NEWS_PAGES,
    ) -> None:
        self._fetcher = fetcher
        self._max_pages = max_pages

    def _fetch_page(self, request: EvidenceRequest, page: int) -> Mapping[str, Any]:
        try:
            return self._fetcher(
                keyword=request.stock_code,
                page_index=page,
                page_size=EASTMONEY_PAGE_SIZE,
            )
        except Exception as exc:
            raise _UpstreamRequestError(str(exc) or exc.__class__.__name__) from exc

    def fetch(self, request: EvidenceRequest) -> SourceResult[NewsItem]:
        if request.capability is not EvidenceCapability.NEWS:
            return SourceResult[NewsItem](
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.UNSUPPORTED,
            )

        try:
            first_page = self._fetch_page(request, 1)
            if _nonnegative_int(first_page.get("code"), "code") != 0:
                raise ValueError(f"东方财富返回错误: {first_page.get('msg', '')}")
            if "hitsTotal" not in first_page:
                raise ValueError("东方财富响应缺少 hitsTotal")
            total = _nonnegative_int(first_page["hitsTotal"], "hitsTotal")
            page_count = math.ceil(total / EASTMONEY_PAGE_SIZE)
            if page_count > self._max_pages:
                raise ValueError(
                    f"东方财富结果 {total} 条，超过安全分页上限 "
                    f"{self._max_pages * EASTMONEY_PAGE_SIZE} 条"
                )

            pages = [first_page]
            pages.extend(
                self._fetch_page(request, page)
                for page in range(2, page_count + 1)
            )
            raw_rows: list[Any] = []
            for payload in pages:
                result = _mapping(payload.get("result"), "东方财富 result")
                raw_rows.extend(
                    _list(
                        result.get("cmsArticleWebOld"),
                        "东方财富 cmsArticleWebOld",
                    )
                )

            if total == 0:
                if raw_rows:
                    raise ValueError("hitsTotal=0 但响应包含新闻")
                return SourceResult[NewsItem](
                    source_id=self.descriptor.source_id,
                    upstream_id=self.descriptor.upstream_id,
                    capability=request.capability,
                    status=SourceStatus.SUCCESS_EMPTY,
                )
            if len(raw_rows) != total:
                raise ValueError(
                    f"东方财富声明 {total} 条，实际返回 {len(raw_rows)} 条"
                )

            items: list[NewsItem] = []
            for raw_row in raw_rows:
                row = _mapping(raw_row, "东方财富新闻条目")
                title = _clean_text(row.get("title"))
                raw_text = _clean_text(row.get("content"))
                reason = _association_reason(
                    f"{title}\n{raw_text}",
                    stock_code=request.stock_code,
                    stock_name=request.stock_name,
                )
                if reason is None or not title:
                    continue
                published_at = _parse_datetime(row.get("date"))
                if not _within_window(published_at, request):
                    continue
                external_id = str(row.get("code", "")).strip()
                if not external_id:
                    raise ValueError("东方财富新闻缺少 code")
                items.append(
                    _news_item(
                        external_id=external_id,
                        request=request,
                        title=title,
                        raw_text=raw_text,
                        published_at=published_at,
                        source_id=self.descriptor.source_id,
                        source_name=self.descriptor.display_name,
                        publisher=_clean_text(row.get("mediaName")) or "东方财富",
                        url=str(row.get("url", "")).strip(),
                        association_reason=reason,
                    )
                )
        except _UpstreamRequestError as exc:
            logger.warning("东方财富新闻请求失败: %s", exc)
            return _failed_result(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                error_code="upstream_request_failed",
                exc=exc,
            )
        except Exception as exc:
            logger.exception("东方财富新闻响应格式无效")
            return _failed_result(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                error_code="invalid_upstream_payload",
                exc=exc,
            )

        return SourceResult[NewsItem](
            source_id=self.descriptor.source_id,
            upstream_id=self.descriptor.upstream_id,
            capability=request.capability,
            status=(
                SourceStatus.SUCCESS_DATA
                if items
                else SourceStatus.SUCCESS_EMPTY
            ),
            items=items,
        )


class SinaNewsSource:
    """新浪财经全局快讯适配器，通过股票代码或名称做本地关联。"""

    descriptor = SourceDescriptor(
        source_id="sina-finance-feed",
        upstream_id="sina",
        display_name="新浪财经快讯",
        capabilities={EvidenceCapability.NEWS},
    )

    def __init__(
        self,
        *,
        fetcher: SinaNewsFetcher = _default_sina_fetcher,
        max_pages: int = MAX_NEWS_PAGES,
    ) -> None:
        self._fetcher = fetcher
        self._max_pages = max_pages

    def _fetch_page(self, page: int) -> Mapping[str, Any]:
        try:
            return self._fetcher(page=page, page_size=SINA_PAGE_SIZE)
        except Exception as exc:
            raise _UpstreamRequestError(str(exc) or exc.__class__.__name__) from exc

    @staticmethod
    def _feed(payload: Mapping[str, Any]) -> tuple[list[Any], int | None]:
        result = _mapping(payload.get("result"), "新浪 result")
        status = _mapping(result.get("status"), "新浪 status")
        if _nonnegative_int(status.get("code"), "新浪 status.code") != 0:
            raise ValueError("新浪返回非零状态码")
        data = _mapping(result.get("data"), "新浪 data")
        feed = _mapping(data.get("feed"), "新浪 feed")
        rows = _list(feed.get("list"), "新浪 feed.list")
        page_info_raw = feed.get("page_info")
        if not isinstance(page_info_raw, Mapping):
            return rows, None
        total_value = page_info_raw.get("totalNum", page_info_raw.get("total"))
        if total_value is None:
            return rows, None
        return rows, _nonnegative_int(total_value, "新浪 total")

    def fetch(self, request: EvidenceRequest) -> SourceResult[NewsItem]:
        if request.capability is not EvidenceCapability.NEWS:
            return SourceResult[NewsItem](
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.UNSUPPORTED,
            )

        try:
            raw_rows: list[Any] = []
            seen_ids: set[str] = set()
            total: int | None = None

            for page in range(1, self._max_pages + 1):
                page_rows, page_total = self._feed(self._fetch_page(page))
                if total is None:
                    total = page_total
                new_rows: list[Any] = []
                for raw_row in page_rows:
                    row = _mapping(raw_row, "新浪新闻条目")
                    row_id = str(row.get("id", "")).strip()
                    if row_id and row_id in seen_ids:
                        continue
                    if row_id:
                        seen_ids.add(row_id)
                    new_rows.append(raw_row)
                raw_rows.extend(new_rows)

                if not page_rows or not new_rows:
                    break
                if total is not None and len(raw_rows) >= total:
                    break
                if len(page_rows) < SINA_PAGE_SIZE:
                    break

            items: list[NewsItem] = []
            oldest_published_at: datetime | None = None
            for raw_row in raw_rows:
                row = _mapping(raw_row, "新浪新闻条目")
                raw_text = _clean_text(row.get("rich_text"))
                published_at = _parse_datetime(row.get("create_time"))
                if (
                    oldest_published_at is None
                    or published_at < oldest_published_at
                ):
                    oldest_published_at = published_at
                reason = _association_reason(
                    raw_text,
                    stock_code=request.stock_code,
                    stock_name=request.stock_name,
                )
                if reason is None or not raw_text:
                    continue
                if not _within_window(published_at, request):
                    continue
                external_id = str(row.get("id", "")).strip()
                if not external_id:
                    raise ValueError("新浪新闻缺少 id")
                title = raw_text[:120]
                items.append(
                    _news_item(
                        external_id=external_id,
                        request=request,
                        title=title,
                        raw_text=raw_text,
                        published_at=published_at,
                        source_id=self.descriptor.source_id,
                        source_name=self.descriptor.display_name,
                        publisher="新浪财经",
                        url=str(row.get("docurl", "")).strip(),
                        association_reason=reason,
                    )
                )
        except _UpstreamRequestError as exc:
            logger.warning("新浪新闻请求失败: %s", exc)
            return _failed_result(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                error_code="upstream_request_failed",
                exc=exc,
            )
        except Exception as exc:
            logger.exception("新浪新闻响应格式无效")
            return _failed_result(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                error_code="invalid_upstream_payload",
                exc=exc,
            )

        window_covered = (
            request.start_at is None
            or not raw_rows
            or (
                oldest_published_at is not None
                and oldest_published_at <= _aware_shanghai(request.start_at)
            )
        )
        if not window_covered:
            return SourceResult[NewsItem](
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.STALE,
                items=items,
                error_code="time_window_not_fully_covered",
                error_message=(
                    "新浪快讯可访问历史未覆盖请求起始时间，"
                    "不能将未命中解释为明确空结果"
                ),
            )

        return SourceResult[NewsItem](
            source_id=self.descriptor.source_id,
            upstream_id=self.descriptor.upstream_id,
            capability=request.capability,
            status=(
                SourceStatus.SUCCESS_DATA
                if items
                else SourceStatus.SUCCESS_EMPTY
            ),
            items=items,
        )


class SinaRollingFeedCollector:
    """Collect recent global Sina feed metadata for durable rolling storage."""

    def __init__(
        self,
        *,
        fetcher: SinaNewsFetcher = _default_sina_fetcher,
        max_pages: int = 2,
    ) -> None:
        if max_pages < 1:
            raise ValueError("max_pages must be at least 1")
        self._source = SinaNewsSource(fetcher=fetcher, max_pages=max_pages)
        self._max_pages = max_pages

    def collect(self) -> list[NewsItem]:
        """Fetch latest pages and return metadata-only, unassociated items."""
        raw_rows: list[Any] = []
        seen_ids: set[str] = set()
        total: int | None = None
        for page in range(1, self._max_pages + 1):
            page_rows, page_total = self._source._feed(  # noqa: SLF001
                self._source._fetch_page(page)  # noqa: SLF001
            )
            if total is None:
                total = page_total
            new_rows: list[Any] = []
            for raw_row in page_rows:
                row = _mapping(raw_row, "新浪新闻条目")
                row_id = str(row.get("id", "")).strip()
                if not row_id:
                    raise ValueError("新浪新闻缺少 id")
                if row_id in seen_ids:
                    continue
                seen_ids.add(row_id)
                new_rows.append(raw_row)
            raw_rows.extend(new_rows)
            if not page_rows or not new_rows:
                break
            if total is not None and len(raw_rows) >= total:
                break
            if len(page_rows) < SINA_PAGE_SIZE:
                break

        request = EvidenceRequest(capability=EvidenceCapability.NEWS)
        items: list[NewsItem] = []
        for raw_row in raw_rows:
            row = _mapping(raw_row, "新浪新闻条目")
            raw_text = _clean_text(row.get("rich_text"))
            if not raw_text:
                continue
            external_id = str(row.get("id", "")).strip()
            published_at = _parse_datetime(row.get("create_time"))
            items.append(
                _news_item(
                    external_id=external_id,
                    request=request,
                    title=raw_text[:500],
                    raw_text=raw_text,
                    published_at=published_at,
                    source_id=SinaNewsSource.descriptor.source_id,
                    source_name=SinaNewsSource.descriptor.display_name,
                    publisher="新浪财经",
                    url=str(row.get("docurl", "")).strip(),
                    association_reason="rolling_feed",
                )
            )
        return items


__all__ = [
    "EastmoneyNewsSource",
    "SinaNewsSource",
    "SinaRollingFeedCollector",
]
