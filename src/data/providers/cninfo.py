"""巨潮资讯公告适配器。

同时保留直连公开端点和 AKShare 两种接入实现，但来源独立性都按真实上游
``cninfo`` 计算。适配器只负责查询和标准化，不负责缓存、重试、聚合或数据库去重。
"""

import logging
import math
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol
from urllib.parse import parse_qs, urlencode, urlparse
from zoneinfo import ZoneInfo

import pandas as pd

from src.data.evidence import (
    EvidenceCapability,
    EvidenceRequest,
    SourceDescriptor,
    SourceResult,
    SourceStatus,
)
from src.data.models import AnnouncementItem

logger = logging.getLogger(__name__)

SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")
CNINFO_STOCK_LIST_URL = "https://www.cninfo.com.cn/new/data/szse_stock.json"
CNINFO_QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_DETAIL_URL = "https://www.cninfo.com.cn/new/disclosure/detail"
CNINFO_STATIC_URL = "https://static.cninfo.com.cn/"
CNINFO_PAGE_SIZE = 30
CNINFO_TIMEOUT_SECONDS = 15.0
CNINFO_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Referer": (
        "https://www.cninfo.com.cn/new/commonUrl/"
        "pageOfSearch?url=disclosure/list/search"
    ),
    "User-Agent": "litchi-head/0.1 (+https://github.com/NoahLightryyy/litchi-head)",
}
REQUIRED_COLUMNS = {
    "代码",
    "简称",
    "公告标题",
    "公告时间",
    "公告链接",
}


class CninfoFetcher(Protocol):
    """AKShare CNINFO 函数的可替换调用边界。"""

    def __call__(
        self,
        *,
        symbol: str,
        market: str,
        keyword: str,
        category: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """获取指定日期范围内的公司公告。"""
        ...


class CninfoDirectFetcher(Protocol):
    """巨潮公开端点的可替换调用边界。"""

    def __call__(
        self,
        *,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> Mapping[str, Any]:
        """返回包含总数和完整公告列表的巨潮原始响应。"""
        ...


def _default_fetcher(
    *,
    symbol: str,
    market: str,
    keyword: str,
    category: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    import akshare as ak

    return ak.stock_zh_a_disclosure_report_cninfo(
        symbol=symbol,
        market=market,
        keyword=keyword,
        category=category,
        start_date=start_date,
        end_date=end_date,
    )


def _parse_nonnegative_int(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} 必须是非负整数")
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} 必须是非负整数") from exc
    if parsed < 0:
        raise ValueError(f"{field_name} 必须是非负整数")
    return parsed


def _response_mapping(value: object, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} 必须是 JSON 对象")
    return value


def _validated_direct_page_items(
    page: Mapping[str, Any],
    *,
    expected_total: int,
    page_number: int,
    page_count: int,
) -> list[Any]:
    if "totalAnnouncement" not in page:
        raise ValueError("公告查询响应缺少 totalAnnouncement")
    page_total = _parse_nonnegative_int(
        page["totalAnnouncement"],
        "totalAnnouncement",
    )
    if page_total != expected_total:
        raise ValueError(
            "totalAnnouncement changed between pages: "
            f"{expected_total} != {page_total}"
        )
    page_items = page.get("announcements")
    if not isinstance(page_items, list):
        raise ValueError("公告查询响应缺少 announcements")
    if page_number < 1 or page_number > page_count:
        raise ValueError("公告查询页码超出完整分页范围")
    expected_count = (
        CNINFO_PAGE_SIZE
        if page_number < page_count
        else expected_total - CNINFO_PAGE_SIZE * (page_count - 1)
    )
    if len(page_items) != expected_count:
        raise ValueError(
            f"announcement page {page_number} expected "
            f"{expected_count} items, got {len(page_items)}"
        )
    return page_items


def _lookup_org_id(stock_payload: object, symbol: str) -> str:
    payload = _response_mapping(stock_payload, "股票列表响应")
    stock_list = payload.get("stockList")
    if not isinstance(stock_list, list):
        raise ValueError("股票列表响应缺少 stockList")

    for raw_item in stock_list:
        if not isinstance(raw_item, Mapping):
            continue
        if str(raw_item.get("code", "")).strip() != symbol:
            continue
        org_id = str(raw_item.get("orgId", "")).strip()
        if not org_id:
            raise ValueError(f"股票 {symbol} 缺少 orgId")
        return org_id
    raise ValueError(f"股票列表中不存在 {symbol}")


def _default_direct_fetcher(
    *,
    symbol: str,
    start_date: str,
    end_date: str,
) -> Mapping[str, Any]:
    """直接调用巨潮公开端点并返回完整、可校验的原始结果。"""
    import httpx

    with httpx.Client(
        headers=CNINFO_HEADERS,
        timeout=CNINFO_TIMEOUT_SECONDS,
        follow_redirects=True,
    ) as client:
        stock_response = client.get(CNINFO_STOCK_LIST_URL)
        stock_response.raise_for_status()
        org_id = _lookup_org_id(stock_response.json(), symbol)

        payload = {
            "pageNum": "1",
            "pageSize": str(CNINFO_PAGE_SIZE),
            "column": "szse",
            "tabName": "fulltext",
            "plate": "",
            "stock": f"{symbol},{org_id}",
            "searchkey": "",
            "secid": "",
            "category": "",
            "trade": "",
            "seDate": (
                f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}~"
                f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
            ),
            "sortName": "",
            "sortType": "",
            "isHLtitle": "false",
        }

        def fetch_page(page_number: int) -> Mapping[str, Any]:
            page_payload = {**payload, "pageNum": str(page_number)}
            response = client.post(CNINFO_QUERY_URL, data=page_payload)
            response.raise_for_status()
            return _response_mapping(response.json(), "公告查询响应")

        first_page = fetch_page(1)
        if "totalAnnouncement" not in first_page:
            raise ValueError("公告查询响应缺少 totalAnnouncement")
        total = _parse_nonnegative_int(
            first_page["totalAnnouncement"],
            "totalAnnouncement",
        )
        page_count = max(1, math.ceil(total / CNINFO_PAGE_SIZE))
        announcements: list[Any] = []

        for page_number in range(1, page_count + 1):
            page = first_page if page_number == 1 else fetch_page(page_number)
            page_items = _validated_direct_page_items(
                page,
                expected_total=total,
                page_number=page_number,
                page_count=page_count,
            )
            announcements.extend(page_items)

    return {
        "totalAnnouncement": total,
        "announcements": announcements,
    }


def _shanghai_date(value: datetime) -> str:
    """将请求边界转换为巨潮资讯所需的上海日期。"""
    if value.tzinfo is None:
        localized = value.replace(tzinfo=SHANGHAI_TIMEZONE)
    else:
        localized = value.astimezone(SHANGHAI_TIMEZONE)
    return localized.strftime("%Y%m%d")


def _normalize_stock_code(value: object) -> str:
    raw = str(value).strip()
    if raw.endswith(".0") and raw[:-2].isdigit():
        raw = raw[:-2]
    return raw.zfill(6)


def _parse_published_at(value: object) -> datetime:
    parsed = pd.to_datetime(str(value), errors="raise")
    if not isinstance(parsed, pd.Timestamp):
        raise ValueError(f"invalid 公告时间: {value!r}")
    result = parsed.to_pydatetime()
    if result.tzinfo is None:
        return result.replace(tzinfo=SHANGHAI_TIMEZONE)
    return result.astimezone(SHANGHAI_TIMEZONE)


def _extract_announcement_id(url: str) -> str:
    values = parse_qs(urlparse(url).query).get("announcementId", [])
    if not values or not values[0].strip():
        raise ValueError("公告链接缺少 announcementId")
    return values[0].strip()


def _exception_message(exc: Exception) -> str:
    return str(exc).strip() or exc.__class__.__name__


def _frame_to_items(frame: pd.DataFrame) -> list[AnnouncementItem]:
    missing_columns = REQUIRED_COLUMNS - set(frame.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"缺少上游字段: {missing}")

    items: list[AnnouncementItem] = []
    for row in frame.to_dict(orient="records"):
        url = str(row["公告链接"]).strip()
        items.append(
            AnnouncementItem(
                external_id=_extract_announcement_id(url),
                stock_code=_normalize_stock_code(row["代码"]),
                stock_name=str(row["简称"]).strip(),
                title=str(row["公告标题"]).strip(),
                published_at=_parse_published_at(row["公告时间"]),
                source_name="巨潮资讯",
                url=url,
            )
        )
    return items


def _required_direct_text(item: Mapping[str, Any], field_name: str) -> str:
    raw_value = item.get(field_name)
    if not isinstance(raw_value, str):
        raise ValueError(f"公告 {field_name} 必须是文本")
    value = raw_value.strip()
    if not value:
        raise ValueError(f"公告缺少 {field_name}")
    return value


def _optional_attachment_url(item: Mapping[str, Any]) -> str | None:
    raw_path = item.get("adjunctUrl")
    if raw_path is None:
        return None
    if not isinstance(raw_path, str):
        raise ValueError("公告 adjunctUrl 必须是文本")
    path = raw_path.strip().lstrip("/")
    if not path:
        return None
    return f"{CNINFO_STATIC_URL}{path}"


def _parse_direct_published_at(value: object) -> datetime:
    milliseconds = _parse_nonnegative_int(value, "announcementTime")
    parsed = pd.to_datetime(milliseconds, unit="ms", utc=True, errors="raise")
    if not isinstance(parsed, pd.Timestamp):
        raise ValueError(f"invalid announcementTime: {value!r}")
    return parsed.to_pydatetime().astimezone(SHANGHAI_TIMEZONE)


def _direct_payload_to_items(payload: object) -> list[AnnouncementItem]:
    response = _response_mapping(payload, "公告查询响应")
    if "totalAnnouncement" not in response:
        raise ValueError("公告查询响应缺少 totalAnnouncement")
    total = _parse_nonnegative_int(
        response["totalAnnouncement"],
        "totalAnnouncement",
    )
    announcements = response.get("announcements")
    if not isinstance(announcements, list):
        raise ValueError("公告查询响应缺少 announcements")
    if len(announcements) != total:
        raise ValueError(
            "totalAnnouncement 与 announcements 数量不一致: "
            f"{total} != {len(announcements)}"
        )

    items: list[AnnouncementItem] = []
    for raw_item in announcements:
        item = _response_mapping(raw_item, "公告记录")
        stock_code = _normalize_stock_code(
            _required_direct_text(item, "secCode")
        )
        announcement_id = _required_direct_text(item, "announcementId")
        org_id = _required_direct_text(item, "orgId")
        url = f"{CNINFO_DETAIL_URL}?{urlencode({
            'stockCode': stock_code,
            'announcementId': announcement_id,
            'orgId': org_id,
        })}"
        items.append(
            AnnouncementItem(
                external_id=announcement_id,
                stock_code=stock_code,
                stock_name=str(item.get("secName", "")).strip(),
                title=_required_direct_text(item, "announcementTitle"),
                published_at=_parse_direct_published_at(
                    item.get("announcementTime")
                ),
                source_name="巨潮资讯",
                url=url,
                attachment_url=_optional_attachment_url(item),
            )
        )
    return items


def _validate_announcement_request(request: EvidenceRequest) -> str | None:
    if not request.stock_code.strip():
        return "stock_code 不能为空"
    if request.start_at is None or request.end_at is None:
        return "start_at 和 end_at 必须显式提供"
    return None


class CninfoDirectAnnouncementSource:
    """直接调用 CNINFO 公开端点的权威公告来源。"""

    descriptor = SourceDescriptor(
        source_id="cninfo-direct",
        upstream_id="cninfo",
        display_name="巨潮资讯公告（直连）",
        capabilities={EvidenceCapability.ANNOUNCEMENT},
        discovery_only=False,
    )

    def __init__(self, fetcher: CninfoDirectFetcher | None = None) -> None:
        self._fetcher = fetcher or _default_direct_fetcher

    def fetch(
        self,
        request: EvidenceRequest,
    ) -> SourceResult[AnnouncementItem]:
        """查询公开端点并严格区分真实空结果与请求失败。"""
        if request.capability is not EvidenceCapability.ANNOUNCEMENT:
            return SourceResult[AnnouncementItem](
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.UNSUPPORTED,
            )

        invalid_reason = _validate_announcement_request(request)
        if invalid_reason is not None:
            logger.warning("CNINFO 直连公告请求无效: %s", invalid_reason)
            return SourceResult[AnnouncementItem](
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.FAILED,
                error_code="invalid_request",
                error_message=invalid_reason,
            )

        assert request.start_at is not None
        assert request.end_at is not None
        try:
            payload = self._fetcher(
                symbol=request.stock_code,
                start_date=_shanghai_date(request.start_at),
                end_date=_shanghai_date(request.end_at),
            )
        except Exception as exc:
            logger.exception(
                "CNINFO 直连公告查询失败: stock_code=%s",
                request.stock_code,
            )
            return SourceResult[AnnouncementItem](
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.FAILED,
                error_code="upstream_request_failed",
                error_message=_exception_message(exc),
            )

        try:
            items = _direct_payload_to_items(payload)
        except Exception as exc:
            logger.exception(
                "CNINFO 直连公告响应格式无效: stock_code=%s",
                request.stock_code,
            )
            return SourceResult[AnnouncementItem](
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.FAILED,
                error_code="invalid_upstream_payload",
                error_message=_exception_message(exc),
            )

        status = (
            SourceStatus.SUCCESS_DATA if items else SourceStatus.SUCCESS_EMPTY
        )
        return SourceResult[AnnouncementItem](
            source_id=self.descriptor.source_id,
            upstream_id=self.descriptor.upstream_id,
            capability=request.capability,
            status=status,
            items=items,
        )


class CninfoAnnouncementSource:
    """通过 AKShare 接入 CNINFO 的权威公告来源。"""

    descriptor = SourceDescriptor(
        source_id="akshare-cninfo",
        upstream_id="cninfo",
        display_name="巨潮资讯公告（AKShare）",
        capabilities={EvidenceCapability.ANNOUNCEMENT},
        discovery_only=False,
    )

    def __init__(self, fetcher: CninfoFetcher | None = None) -> None:
        self._fetcher = fetcher or _default_fetcher

    def fetch(
        self,
        request: EvidenceRequest,
    ) -> SourceResult[AnnouncementItem]:
        """查询并严格标准化指定股票的公告。"""
        if request.capability is not EvidenceCapability.ANNOUNCEMENT:
            return SourceResult[AnnouncementItem](
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.UNSUPPORTED,
            )

        invalid_reason = _validate_announcement_request(request)
        if invalid_reason is not None:
            logger.warning("CNINFO 公告请求无效: %s", invalid_reason)
            return SourceResult[AnnouncementItem](
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.FAILED,
                error_code="invalid_request",
                error_message=invalid_reason,
            )

        assert request.start_at is not None
        assert request.end_at is not None
        try:
            frame = self._fetcher(
                symbol=request.stock_code,
                market="沪深京",
                keyword="",
                category="",
                start_date=_shanghai_date(request.start_at),
                end_date=_shanghai_date(request.end_at),
            )
        except Exception as exc:
            logger.exception("CNINFO 公告查询失败: stock_code=%s", request.stock_code)
            return SourceResult[AnnouncementItem](
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.FAILED,
                error_code="upstream_request_failed",
                error_message=_exception_message(exc),
            )

        if frame.empty:
            return SourceResult[AnnouncementItem](
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.SUCCESS_EMPTY,
            )

        try:
            items = _frame_to_items(frame)
        except Exception as exc:
            logger.exception(
                "CNINFO 公告响应格式无效: stock_code=%s",
                request.stock_code,
            )
            return SourceResult[AnnouncementItem](
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.FAILED,
                error_code="invalid_upstream_payload",
                error_message=_exception_message(exc),
            )

        return SourceResult[AnnouncementItem](
            source_id=self.descriptor.source_id,
            upstream_id=self.descriptor.upstream_id,
            capability=request.capability,
            status=SourceStatus.SUCCESS_DATA,
            items=items,
        )

__all__ = [
    "CninfoAnnouncementSource",
    "CninfoDirectAnnouncementSource",
]
