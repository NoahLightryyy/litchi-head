"""Official CNINFO corporate-action terms parsed from implementation notices."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from fractions import Fraction
from typing import Any
from urllib.parse import urlencode

from src.data.kline import MarketCode
from src.data.kline_adjustment import (
    ActionKind,
    OfficialCorporateActionDocument,
    OfficialCorporateActionEvent,
    is_supported_a_share_code,
    market_code_for,
)
from src.data.providers.cninfo import (
    CNINFO_DETAIL_URL,
    CNINFO_STATIC_URL,
    CninfoDirectFetcher,
    _default_direct_fetcher,
    _parse_direct_published_at,
)
from src.data.providers.cninfo_status import (
    OfficialDocumentFetcher,
    _default_document_fetcher,
    _parse_total,
    _required_text,
)

CNINFO_CORPORATE_ACTION_SOURCE_ID = "cninfo-corporate-action"
CNINFO_CORPORATE_ACTION_UPSTREAM_ID = "cninfo"
CNINFO_CORPORATE_ACTION_PARSER_VERSION = "cninfo-corporate-action-v1"

_DATE_BODY = (
    r"(?P<year>\d{4})\s*年\s*"
    r"(?P<month>\d{1,2})\s*月\s*"
    r"(?P<day>\d{1,2})\s*日"
)
_RECORD_DATE_PATTERN = re.compile(rf"股权登记日为?[:：]?\s*{_DATE_BODY}")
_EX_DATE_PATTERN = re.compile(rf"除权(?:除息)?日为?[:：]?\s*{_DATE_BODY}")
_IMPLEMENTATION_SECTION_PATTERN = re.compile(
    r"二[、.]本次实施的权益分派方案(?P<body>.*?)"
    r"三[、.]股权登记日",
    re.DOTALL,
)
_DISTRIBUTION_DATE_SECTION_PATTERN = re.compile(
    r"三[、.]股权登记日与除权除息日(?P<body>.*?)(?=\n\s*四[、.]|\Z)",
    re.DOTALL,
)
_CASH_PATTERN = re.compile(
    r"每\s*(?P<base>\d+)\s*股\s*派(?:发)?"
    r"(?:现金股利)?(?:人民币)?\s*"
    r"(?P<amount>\d+(?:\.\d+)?)\s*元"
)
_SEND_PATTERN = re.compile(
    r"每\s*(?P<base>\d+)\s*股\s*送(?:红股)?\s*"
    r"(?P<shares>\d+(?:\.\d+)?)\s*股"
)
_TRANSFER_PATTERN = re.compile(
    r"每\s*(?P<base>\d+)\s*股\s*转增\s*"
    r"(?P<shares>\d+(?:\.\d+)?)\s*股"
)


class CorporateActionSourceError(RuntimeError):
    """Official corporate-action evidence is incomplete or unavailable."""


@dataclass(frozen=True)
class _ParsedNotice:
    record_date: date
    ex_date: date
    document: OfficialCorporateActionDocument
    cash_dividend_per_share: Decimal | None
    share_ratio: Fraction | None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _date_from_match(match: re.Match[str]) -> date:
    return date(
        int(match.group("year")),
        int(match.group("month")),
        int(match.group("day")),
    )


def _unique_date(
    pattern: re.Pattern[str],
    text: str,
    label: str,
) -> date:
    values = {_date_from_match(match) for match in pattern.finditer(text)}
    if not values:
        raise ValueError(
            f"official corporate-action notice lacks {label}"
        )
    if len(values) != 1:
        raise ValueError(
            f"official corporate-action {label} values conflict"
        )
    return next(iter(values))


def _cash_term(section_body: str) -> tuple[Decimal, Decimal] | None:
    gross_candidates: set[tuple[Decimal, Decimal]] = set()
    fallback_candidates: set[tuple[Decimal, Decimal]] = set()
    for match in _CASH_PATTERN.finditer(section_body):
        candidate = (
            Decimal(match.group("base")),
            Decimal(match.group("amount")),
        )
        if "含税" in section_body[match.end() : match.end() + 40]:
            gross_candidates.add(candidate)
            continue
        segment_start = max(
            section_body.rfind(mark, 0, match.start())
            for mark in ("。", "；", "\n")
        )
        context = section_body[segment_start + 1 : match.start()]
        if any(
            marker in context
            for marker in ("扣税后", "税后", "补缴税款")
        ):
            continue
        fallback_candidates.add(candidate)
    candidates = gross_candidates or fallback_candidates
    if len(candidates) > 1:
        raise ValueError(
            "official corporate-action cash terms conflict"
        )
    return next(iter(candidates), None)


def _share_term(
    pattern: re.Pattern[str],
    section_body: str,
    label: str,
) -> tuple[Decimal, Decimal] | None:
    candidates = {
        (
            Decimal(match.group("base")),
            Decimal(match.group("shares")),
        )
        for match in pattern.finditer(section_body)
    }
    if len(candidates) > 1:
        raise ValueError(
            f"official corporate-action {label} terms conflict"
        )
    return next(iter(candidates), None)


def _per_share_amount(amount: Decimal, base: int) -> Decimal:
    power = len(str(base)) - 1
    if base <= 0 or base != 10**power:
        raise ValueError(
            "official corporate-action cash base must be a power of ten"
        )
    return amount.scaleb(-power)


def _attachment_url(item: Mapping[str, Any]) -> str:
    path = _required_text(item, "adjunctUrl").lstrip("/")
    return f"{CNINFO_STATIC_URL}{path}"


def _detail_url(item: Mapping[str, Any], code: str) -> str:
    return f"{CNINFO_DETAIL_URL}?{urlencode({
        'stockCode': code,
        'announcementId': _required_text(item, 'announcementId'),
        'orgId': _required_text(item, 'orgId'),
    })}"


class CninfoCorporateActionSource:
    """Parse auditable corporate-action terms from complete CNINFO queries."""

    def __init__(
        self,
        announcement_fetcher: CninfoDirectFetcher | None = None,
        document_fetcher: OfficialDocumentFetcher | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._announcement_fetcher = (
            announcement_fetcher or _default_direct_fetcher
        )
        self._document_fetcher = document_fetcher or _default_document_fetcher
        self._clock = clock or _utc_now

    def fetch_events(
        self,
        *,
        code: str,
        market: MarketCode,
        start: date,
        end: date,
    ) -> tuple[OfficialCorporateActionEvent, ...]:
        """Return official implementation terms collected within one query."""
        if not is_supported_a_share_code(code):
            raise CorporateActionSourceError(
                "corporate-action code is not a supported A-share"
            )
        if market is not market_code_for(code):
            raise CorporateActionSourceError(
                "corporate-action code and market do not match"
            )
        if market is MarketCode.SSE:
            raise CorporateActionSourceError(
                "CNINFO SSE corporate-action template is unsupported"
            )
        if market is MarketCode.BSE:
            raise CorporateActionSourceError(
                "CNINFO BSE corporate-action coverage is not verified"
            )
        if start > end:
            raise CorporateActionSourceError(
                "corporate-action start must not exceed end"
            )

        try:
            payload = self._announcement_fetcher(
                symbol=code,
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )
            if not isinstance(payload, Mapping):
                raise ValueError("official announcement payload must be an object")
            _, announcements = _parse_total(payload)
            announcement_ids: list[str] = []
            for raw_item in announcements:
                if not isinstance(raw_item, Mapping):
                    raise ValueError(
                        "official announcement item must be an object"
                    )
                announcement_ids.append(
                    _required_text(raw_item, "announcementId")
                )
            if len(set(announcement_ids)) != len(announcement_ids):
                raise ValueError(
                    "official announcement payload contains duplicate identities"
                )
            notices: list[_ParsedNotice] = []
            for raw_item in announcements:
                assert isinstance(raw_item, Mapping)
                if _required_text(raw_item, "secCode") != code:
                    raise ValueError("official announcement stock code mismatch")
                title = _required_text(raw_item, "announcementTitle")
                is_corporate_action_title = (
                    "权益分派" in title or "配股" in title
                )
                if is_corporate_action_title and any(
                    marker in title
                    for marker in (
                        "更正",
                        "补充",
                        "修订",
                        "延期",
                        "终止",
                        "取消",
                        "变更",
                        "调整",
                    )
                ):
                    raise ValueError(
                        "official corporate-action lifecycle or revision "
                        "notice requires an explicit revision ledger"
                    )
                is_distribution = title.endswith("权益分派实施公告")
                is_rights_issue = title.endswith("配股发行公告")
                if is_rights_issue:
                    raise ValueError(
                        "official rights template is unsupported"
                    )
                if not is_distribution:
                    continue

                attachment_url = _attachment_url(raw_item)
                official_document = self._document_fetcher(attachment_url)
                document_text = official_document.text
                if (
                    "差异化分红" in document_text
                    or "差异化权益分派" in document_text
                    or "按总股本折算" in document_text
                    or (
                        "回购专用" in document_text
                        and "不参与" in document_text
                    )
                ):
                    raise ValueError(
                        "official differential distribution basis is unsupported"
                    )
                date_section_match = (
                    _DISTRIBUTION_DATE_SECTION_PATTERN.search(document_text)
                )
                date_body = (
                    date_section_match.group("body")
                    if date_section_match is not None
                    else ""
                )
                record_date = _unique_date(
                    _RECORD_DATE_PATTERN,
                    date_body,
                    "record date",
                )
                ex_date = _unique_date(
                    _EX_DATE_PATTERN,
                    date_body,
                    "ex date",
                )
                amount: Decimal | None = None
                share_ratio: Fraction | None = None
                section_match = _IMPLEMENTATION_SECTION_PATTERN.search(
                    document_text
                )
                if section_match is None:
                    raise ValueError(
                        "official corporate-action notice lacks "
                        "implementation section"
                    )
                section_body = section_match.group("body")
                cash_term = _cash_term(section_body)
                cash_base = cash_term[0] if cash_term is not None else None
                amount = (
                    _per_share_amount(
                        cash_term[1],
                        int(cash_term[0]),
                    )
                    if cash_term is not None
                    else None
                )
                share_terms = tuple(
                    term
                    for term in (
                        _share_term(_SEND_PATTERN, section_body, "send"),
                        _share_term(
                            _TRANSFER_PATTERN,
                            section_body,
                            "transfer",
                        ),
                    )
                    if term is not None
                )
                if share_terms:
                    share_bases = {term[0] for term in share_terms}
                    if len(share_bases) != 1:
                        raise ValueError(
                            "official corporate-action share bases conflict"
                        )
                    share_base = next(iter(share_bases))
                    if cash_base is not None and share_base != cash_base:
                        raise ValueError(
                            "official corporate-action term bases conflict"
                        )
                    added_shares = sum(
                        (term[1] for term in share_terms),
                        Decimal(0),
                    )
                    share_ratio = Fraction(
                        share_base + added_shares
                    ) / Fraction(share_base)
                if amount is None and share_ratio is None:
                    raise ValueError(
                        "official corporate-action notice lacks supported terms"
                    )
                published_at = _parse_direct_published_at(
                    raw_item.get("announcementTime")
                )
                announcement_id = _required_text(
                    raw_item,
                    "announcementId",
                )
                notices.append(
                    _ParsedNotice(
                        record_date=record_date,
                        ex_date=ex_date,
                        document=OfficialCorporateActionDocument(
                            external_id=announcement_id,
                            title=title,
                            published_at=published_at,
                            source_url=_detail_url(raw_item, code),
                            attachment_url=attachment_url,
                            content_hash=official_document.content_hash,
                        ),
                        cash_dividend_per_share=amount,
                        share_ratio=share_ratio,
                    )
                )
            events: list[OfficialCorporateActionEvent] = []
            if notices:
                collected_at = self._clock()
                notices_by_ex_date: dict[date, list[_ParsedNotice]] = {}
                for notice in notices:
                    notices_by_ex_date.setdefault(notice.ex_date, []).append(
                        notice
                    )
                for ex_date, same_day in notices_by_ex_date.items():
                    record_dates = {notice.record_date for notice in same_day}
                    cash_values = {
                        notice.cash_dividend_per_share
                        for notice in same_day
                        if notice.cash_dividend_per_share is not None
                    }
                    share_ratios = {
                        notice.share_ratio
                        for notice in same_day
                        if notice.share_ratio is not None
                    }
                    if (
                        len(record_dates) != 1
                        or len(cash_values) > 1
                        or len(share_ratios) > 1
                    ):
                        raise ValueError(
                            "official corporate-action notices conflict"
                        )
                    cash_value = next(iter(cash_values), None)
                    aggregate_share_ratio = next(iter(share_ratios), None)
                    component_count = sum(
                        (
                            cash_value is not None,
                            aggregate_share_ratio is not None,
                        )
                    )
                    if component_count >= 2:
                        action_kind: ActionKind = "composite"
                    elif aggregate_share_ratio is not None:
                        action_kind = "share_change"
                    else:
                        action_kind = "cash_dividend"
                    events.append(
                        OfficialCorporateActionEvent(
                            action_id=(
                                f"cninfo:{code}:{ex_date.isoformat()}"
                            ),
                            revision=1,
                            code=code,
                            market=market,
                            record_date=next(iter(record_dates)),
                            ex_date=ex_date,
                            action_kind=action_kind,
                            collected_at=collected_at,
                            source_id=CNINFO_CORPORATE_ACTION_SOURCE_ID,
                            upstream_id=CNINFO_CORPORATE_ACTION_UPSTREAM_ID,
                            parser_version=(
                                CNINFO_CORPORATE_ACTION_PARSER_VERSION
                            ),
                            documents=tuple(
                                notice.document for notice in same_day
                            ),
                            cash_dividend_per_share=cash_value,
                            share_ratio_numerator=(
                                aggregate_share_ratio.numerator
                                if aggregate_share_ratio is not None
                                else None
                            ),
                            share_ratio_denominator=(
                                aggregate_share_ratio.denominator
                                if aggregate_share_ratio is not None
                                else None
                            ),
                        )
                    )
        except CorporateActionSourceError:
            raise
        except Exception as exc:
            message = str(exc).strip() or exc.__class__.__name__
            raise CorporateActionSourceError(message) from exc

        return tuple(
            sorted(
                events,
                key=lambda event: (event.ex_date, event.action_id),
            )
        )


__all__ = [
    "CNINFO_CORPORATE_ACTION_PARSER_VERSION",
    "CninfoCorporateActionSource",
    "CorporateActionSourceError",
]
