"""巨潮资讯公告适配器。

当前通过 AKShare 调用巨潮资讯，但来源独立性按真实上游 ``cninfo`` 计算。
适配器只负责查询和标准化，不负责缓存、重试、聚合或数据库去重。
"""

import logging
from datetime import datetime
from typing import Protocol
from urllib.parse import parse_qs, urlparse
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

        invalid_reason = self._validate_request(request)
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
                error_message=str(exc),
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
                error_message=str(exc),
            )

        return SourceResult[AnnouncementItem](
            source_id=self.descriptor.source_id,
            upstream_id=self.descriptor.upstream_id,
            capability=request.capability,
            status=SourceStatus.SUCCESS_DATA,
            items=items,
        )

    @staticmethod
    def _validate_request(request: EvidenceRequest) -> str | None:
        if not request.stock_code.strip():
            return "stock_code 不能为空"
        if request.start_at is None or request.end_at is None:
            return "start_at 和 end_at 必须显式提供"
        return None


__all__ = ["CninfoAnnouncementSource"]
