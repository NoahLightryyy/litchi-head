"""Official CNINFO corporate-action terms parsed from implementation notices."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from typing import Any
from urllib.parse import urlencode

from src.data.kline import MarketCode
from src.data.kline_adjustment import (
    ActionKind,
    CorporateActionRevisionLedger,
    CorporateActionRevisionStatus,
    OfficialCorporateActionDocument,
    OfficialCorporateActionEvent,
    OfficialCorporateActionRevision,
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
    OfficialDocument,
    OfficialDocumentFetcher,
    _default_document_fetcher,
    _parse_total,
    _required_text,
)

CNINFO_CORPORATE_ACTION_SOURCE_ID = "cninfo-corporate-action"
CNINFO_CORPORATE_ACTION_UPSTREAM_ID = "cninfo"
CNINFO_CORPORATE_ACTION_PARSER_VERSION = "cninfo-corporate-action-v3"
CNINFO_CORPORATE_ACTION_HISTORY_LOOKBACK_DAYS = 365

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
_SSE_DATE_ROW_PATTERN = re.compile(
    r"(?:普通股\s+)?(?P<record_year>\d{4})/(?P<record_month>\d{1,2})/"
    r"(?P<record_day>\d{1,2})\s+(?:(?:－|-|—)\s+)?"
    r"(?P<ex_year>\d{4})/(?P<ex_month>\d{1,2})/(?P<ex_day>\d{1,2})"
)
_SSE_CASH_PATTERN = re.compile(r"每股(?:派发)?现金红利(?:人民币)?\s*(?P<amount>\d+(?:\.\d+)?)\s*元")
_SSE_CURRENT_TOTAL_PATTERN = re.compile(
    r"截至本公告披露日.*?总股本(?:为)?\s*(?P<shares>[\d,]+)\s*股",
    re.DOTALL,
)
_SSE_PARTICIPATING_PATTERN = re.compile(r"本次发放现金红利的股本基数为\s*(?P<shares>[\d,]+)\s*股")
_SSE_VIRTUAL_CASH_PATTERN = re.compile(
    r"虚拟分派的现金红利.*?[≈=]\s*(?P<amount>\d+(?:\.\d+)?)\s*元/股",
    re.DOTALL,
)
_RIGHTS_SECTION_PATTERN = re.compile(
    r"二[、.]本次配股发行方案(?P<body>.*)",
    re.DOTALL,
)
_RIGHTS_RATIO_PATTERN = re.compile(r"每\s*(?P<base>\d+)\s*股配售\s*(?P<shares>\d+)\s*股")
_RIGHTS_PRICE_PATTERN = re.compile(r"配股价格(?:为)?[:：]?\s*(?P<price>\d+(?:\.\d+)?)\s*元/股")


class CorporateActionSourceError(RuntimeError):
    """Official corporate-action evidence is incomplete or unavailable."""


@dataclass(frozen=True)
class _ParsedNotice:
    record_date: date
    ex_date: date
    document: OfficialCorporateActionDocument
    distribution_cash_per_share: Decimal | None
    adjustment_cash_per_share: Decimal | None
    total_shares: int | None
    participating_shares: int | None
    share_ratio: Fraction | None
    rights_ratio: Fraction | None
    rights_subscription_price: Decimal | None
    action_id: str | None
    revision: int


@dataclass(frozen=True)
class _FetchedAnnouncement:
    document_text: str
    document: OfficialCorporateActionDocument


@dataclass(frozen=True)
class _EffectiveAnnouncement:
    fetched: _FetchedAnnouncement
    action_id: str | None
    revision: int


_REVISION_MARKERS: tuple[tuple[str, CorporateActionRevisionStatus], ...] = (
    ("终止", "terminated"),
    ("取消", "cancelled"),
    ("延期", "delayed"),
    ("更正", "corrected"),
    ("补充", "supplemented"),
    ("修订", "corrected"),
    ("变更", "changed"),
    ("调整", "adjusted"),
)
_REPLACEMENT_FULL_PATTERN = re.compile(
    r"(?:权益分派实施公告|配股发行公告)[（(](?:更正|补充|修订|变更|调整)后[）)]$"
)


def _is_corporate_action_title(title: str) -> bool:
    return "权益分派" in title or "配股" in title


def _is_replacement_full_title(title: str) -> bool:
    return _REPLACEMENT_FULL_PATTERN.search(title) is not None


def _is_implementation_title(title: str) -> bool:
    return (
        title.endswith("权益分派实施公告")
        or title.endswith("配股发行公告")
        or _is_replacement_full_title(title)
    )


def _revision_status(title: str) -> CorporateActionRevisionStatus | None:
    if _is_replacement_full_title(title):
        return None
    return next((status for marker, status in _REVISION_MARKERS if marker in title), None)


def _mentions(document_text: str, announcement: _FetchedAnnouncement) -> bool:
    external_id = re.escape(announcement.document.external_id)
    return (
        re.search(rf"(?<![0-9A-Za-z_-]){external_id}(?![0-9A-Za-z_-])", document_text) is not None
        or announcement.document.title in document_text
    )


def _official_document(
    item: Mapping[str, Any],
    *,
    code: str,
    attachment_url: str,
    fetched: OfficialDocument,
) -> OfficialCorporateActionDocument:
    return OfficialCorporateActionDocument(
        external_id=_required_text(item, "announcementId"),
        title=_required_text(item, "announcementTitle"),
        published_at=_parse_direct_published_at(item.get("announcementTime")),
        source_url=_detail_url(item, code),
        attachment_url=attachment_url,
        content_hash=fetched.content_hash,
    )


def _validated_announcements(payload: object) -> list[Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("official announcement payload must be an object")
    _, announcements = _parse_total(payload)
    announcement_ids: list[str] = []
    for raw_item in announcements:
        if not isinstance(raw_item, Mapping):
            raise ValueError("official announcement item must be an object")
        announcement_ids.append(_required_text(raw_item, "announcementId"))
    if len(set(announcement_ids)) != len(announcement_ids):
        raise ValueError("official announcement payload contains duplicate identities")
    return announcements


def _contains_lifecycle_notice(announcements: list[Any]) -> bool:
    return any(
        isinstance(item, Mapping)
        and _revision_status(_required_text(item, "announcementTitle")) is not None
        for item in announcements
    )


def _contains_original_implementation(announcements: list[Any]) -> bool:
    return any(
        isinstance(item, Mapping)
        and _is_implementation_title(_required_text(item, "announcementTitle"))
        and not _is_replacement_full_title(_required_text(item, "announcementTitle"))
        for item in announcements
    )


def _merge_announcements(current: list[Any], history: list[Any]) -> list[Any]:
    merged: dict[str, Any] = {}
    for raw_item in (*history, *current):
        assert isinstance(raw_item, Mapping)
        announcement_id = _required_text(raw_item, "announcementId")
        existing = merged.get(announcement_id)
        if existing is not None and existing != raw_item:
            raise ValueError("official announcement identity changed during history backfill")
        merged[announcement_id] = raw_item
    return list(merged.values())


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
        raise ValueError(f"official corporate-action notice lacks {label}")
    if len(values) != 1:
        raise ValueError(f"official corporate-action {label} values conflict")
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
            section_body.rfind(mark, 0, match.start()) for mark in ("。", "；", "\n")
        )
        context = section_body[segment_start + 1 : match.start()]
        if any(marker in context for marker in ("扣税后", "税后", "补缴税款")):
            continue
        fallback_candidates.add(candidate)
    candidates = gross_candidates or fallback_candidates
    if len(candidates) > 1:
        raise ValueError("official corporate-action cash terms conflict")
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
        raise ValueError(f"official corporate-action {label} terms conflict")
    return next(iter(candidates), None)


def _per_share_amount(amount: Decimal, base: int) -> Decimal:
    power = len(str(base)) - 1
    if base <= 0 or base != 10**power:
        raise ValueError("official corporate-action cash base must be a power of ten")
    return amount.scaleb(-power)


def _sse_distribution_terms(
    text: str,
) -> tuple[date, date, Decimal, Decimal, int | None, int | None]:
    date_rows = tuple(_SSE_DATE_ROW_PATTERN.finditer(text))
    if len(date_rows) != 1:
        raise ValueError("official SSE distribution date row is missing or conflicting")
    row = date_rows[0]
    record_date = date(
        int(row.group("record_year")),
        int(row.group("record_month")),
        int(row.group("record_day")),
    )
    ex_date = date(
        int(row.group("ex_year")),
        int(row.group("ex_month")),
        int(row.group("ex_day")),
    )
    cash_values = {Decimal(match.group("amount")) for match in _SSE_CASH_PATTERN.finditer(text)}
    if len(cash_values) != 1:
        raise ValueError("official SSE distribution cash terms are missing or conflicting")
    distribution = next(iter(cash_values))
    differential = "差异化分红送转：是" in text
    if not differential:
        return record_date, ex_date, distribution, distribution, None, None
    total_match = _SSE_CURRENT_TOTAL_PATTERN.search(text)
    participating_match = _SSE_PARTICIPATING_PATTERN.search(text)
    adjustment_match = _SSE_VIRTUAL_CASH_PATTERN.search(text)
    if total_match is None or participating_match is None or adjustment_match is None:
        raise ValueError("official SSE differential distribution basis is incomplete")
    return (
        record_date,
        ex_date,
        distribution,
        Decimal(adjustment_match.group("amount")),
        int(total_match.group("shares").replace(",", "")),
        int(participating_match.group("shares").replace(",", "")),
    )


def _rights_terms(text: str) -> tuple[date, date, Fraction, Decimal]:
    section_match = _RIGHTS_SECTION_PATTERN.search(text)
    if section_match is None:
        raise ValueError("official rights notice lacks final issuance section")
    section = section_match.group("body")
    ratio_values = {
        Fraction(int(match.group("shares")), int(match.group("base")))
        for match in _RIGHTS_RATIO_PATTERN.finditer(section)
    }
    price_values = {
        Decimal(match.group("price")) for match in _RIGHTS_PRICE_PATTERN.finditer(section)
    }
    if len(ratio_values) != 1 or len(price_values) != 1:
        raise ValueError("official rights issue terms are missing or conflicting")
    return (
        _unique_date(_RECORD_DATE_PATTERN, section, "record date"),
        _unique_date(_EX_DATE_PATTERN, section, "ex date"),
        next(iter(ratio_values)),
        next(iter(price_values)),
    )


def _attachment_url(item: Mapping[str, Any]) -> str:
    path = _required_text(item, "adjunctUrl").lstrip("/")
    return f"{CNINFO_STATIC_URL}{path}"


def _detail_url(item: Mapping[str, Any], code: str) -> str:
    return f"{CNINFO_DETAIL_URL}?{
        urlencode(
            {
                'stockCode': code,
                'announcementId': _required_text(item, 'announcementId'),
                'orgId': _required_text(item, 'orgId'),
            }
        )
    }"


def _resolve_lifecycle(
    announcements: list[Any],
    *,
    code: str,
    document_fetcher: OfficialDocumentFetcher,
) -> tuple[_EffectiveAnnouncement, ...]:
    fetched_by_id: dict[str, _FetchedAnnouncement] = {}
    for raw_item in announcements:
        if not isinstance(raw_item, Mapping):
            raise ValueError("official announcement item must be an object")
        if _required_text(raw_item, "secCode") != code:
            raise ValueError("official announcement stock code mismatch")
        title = _required_text(raw_item, "announcementTitle")
        if not _is_corporate_action_title(title):
            continue
        status = _revision_status(title)
        if not _is_implementation_title(title) and status is None:
            continue
        attachment_url = _attachment_url(raw_item)
        downloaded = document_fetcher(attachment_url)
        document = _official_document(
            raw_item,
            code=code,
            attachment_url=attachment_url,
            fetched=downloaded,
        )
        fetched_by_id[document.external_id] = _FetchedAnnouncement(
            document_text=downloaded.text,
            document=document,
        )

    ordered = tuple(
        sorted(
            fetched_by_id.values(),
            key=lambda item: (item.document.published_at, item.document.external_id),
        )
    )
    originals = tuple(
        item
        for item in ordered
        if _is_implementation_title(item.document.title)
        and not _is_replacement_full_title(item.document.title)
    )
    revisions = tuple(item for item in ordered if _revision_status(item.document.title) is not None)
    replacements = tuple(
        item for item in ordered if _is_replacement_full_title(item.document.title)
    )
    if (revisions or replacements) and not originals:
        raise ValueError(
            "official corporate-action lifecycle notice must be uniquely linked "
            "to an implementation announcement"
        )

    chain_revisions: dict[str, list[OfficialCorporateActionRevision]] = {
        original.document.external_id: [
            OfficialCorporateActionRevision(
                revision=1,
                status="active",
                document=original.document,
            )
        ]
        for original in originals
    }
    chain_documents: dict[str, list[_FetchedAnnouncement]] = {
        original.document.external_id: [original] for original in originals
    }
    used_replacements: set[str] = set()

    for revision_notice in revisions:
        matching_roots = [
            root_id
            for root_id, documents in chain_documents.items()
            if any(
                document.document.published_at <= revision_notice.document.published_at
                and _mentions(revision_notice.document_text, document)
                for document in documents
            )
        ]
        if len(matching_roots) != 1:
            raise ValueError(
                "official corporate-action lifecycle notice must be uniquely linked; "
                "the reference is missing or ambiguous"
            )
        root_id = matching_roots[0]
        status = _revision_status(revision_notice.document.title)
        assert status is not None
        prior_ledger = CorporateActionRevisionLedger(
            code=code,
            market=market_code_for(code),
            revisions=tuple(chain_revisions[root_id]),
        )
        superseded_ids = tuple(
            document.external_id for document in prior_ledger.effective_documents
        )
        if not superseded_ids:
            raise ValueError(
                "official corporate-action lifecycle notice cannot revise a terminal chain"
            )
        chain_revisions[root_id].append(
            OfficialCorporateActionRevision(
                revision=len(chain_revisions[root_id]) + 1,
                status=status,
                document=revision_notice.document,
                supersedes_document_ids=superseded_ids,
            )
        )
        chain_documents[root_id].append(revision_notice)

        if status in {"delayed", "terminated", "cancelled"}:
            continue
        replacement_candidates = [
            replacement
            for replacement in replacements
            if replacement.document.external_id not in used_replacements
            and replacement.document.published_at >= revision_notice.document.published_at
            and (
                _mentions(replacement.document_text, revision_notice)
                or any(
                    _mentions(replacement.document_text, document)
                    for document in chain_documents[root_id][:-1]
                )
            )
        ]
        if len(replacement_candidates) != 1:
            raise ValueError(
                "official corporate-action revision requires one uniquely linked "
                "corrected full implementation announcement"
            )
        replacement = replacement_candidates[0]
        used_replacements.add(replacement.document.external_id)
        chain_revisions[root_id].append(
            OfficialCorporateActionRevision(
                revision=len(chain_revisions[root_id]) + 1,
                status=status,
                document=replacement.document,
                supersedes_document_ids=(revision_notice.document.external_id,),
            )
        )
        chain_documents[root_id].append(replacement)

    unused_replacements = {
        replacement.document.external_id for replacement in replacements
    } - used_replacements
    if unused_replacements:
        raise ValueError(
            "official corrected full implementation announcement lacks a uniquely linked "
            "revision notice"
        )

    results: list[_EffectiveAnnouncement] = []
    for original in originals:
        root_id = original.document.external_id
        ledger = CorporateActionRevisionLedger(
            code=code,
            market=market_code_for(code),
            revisions=tuple(chain_revisions[root_id]),
        )
        if not ledger.can_generate_event:
            continue
        for document in ledger.effective_documents:
            effective = fetched_by_id[document.external_id]
            results.append(
                _EffectiveAnnouncement(
                    fetched=effective,
                    action_id=(f"cninfo:{code}:{root_id}" if len(ledger.revisions) > 1 else None),
                    revision=len(ledger.revisions),
                )
            )
    return tuple(results)


class CninfoCorporateActionSource:
    """Parse auditable corporate-action terms from complete CNINFO queries."""

    def __init__(
        self,
        announcement_fetcher: CninfoDirectFetcher | None = None,
        document_fetcher: OfficialDocumentFetcher | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._announcement_fetcher = announcement_fetcher or _default_direct_fetcher
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
            raise CorporateActionSourceError("corporate-action code is not a supported A-share")
        if market is not market_code_for(code):
            raise CorporateActionSourceError("corporate-action code and market do not match")
        if market is MarketCode.BSE:
            raise CorporateActionSourceError("CNINFO BSE corporate-action coverage is not verified")
        if start > end:
            raise CorporateActionSourceError("corporate-action start must not exceed end")

        try:
            payload = self._announcement_fetcher(
                symbol=code,
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )
            announcements = _validated_announcements(payload)
            if _contains_lifecycle_notice(announcements) and not _contains_original_implementation(
                announcements
            ):
                history_end = start - timedelta(days=1)
                history_start = start - timedelta(
                    days=CNINFO_CORPORATE_ACTION_HISTORY_LOOKBACK_DAYS
                )
                history_payload = self._announcement_fetcher(
                    symbol=code,
                    start_date=history_start.strftime("%Y%m%d"),
                    end_date=history_end.strftime("%Y%m%d"),
                )
                announcements = _merge_announcements(
                    announcements,
                    _validated_announcements(history_payload),
                )
            effective_announcements = _resolve_lifecycle(
                announcements,
                code=code,
                document_fetcher=self._document_fetcher,
            )
            notices: list[_ParsedNotice] = []
            for effective_announcement in effective_announcements:
                fetched_announcement = effective_announcement.fetched
                title = fetched_announcement.document.title
                is_rights_issue = "配股发行公告" in title
                document_text = fetched_announcement.document_text
                if market is not MarketCode.SSE and (
                    "差异化分红" in document_text
                    or "差异化权益分派" in document_text
                    or "按总股本折算" in document_text
                    or ("回购专用" in document_text and "不参与" in document_text)
                ):
                    raise ValueError("official differential distribution basis is unsupported")
                amount: Decimal | None = None
                adjustment_amount: Decimal | None = None
                total_shares: int | None = None
                participating_shares: int | None = None
                share_ratio: Fraction | None = None
                rights_ratio: Fraction | None = None
                rights_subscription_price: Decimal | None = None
                if is_rights_issue:
                    (
                        record_date,
                        ex_date,
                        rights_ratio,
                        rights_subscription_price,
                    ) = _rights_terms(document_text)
                elif market is MarketCode.SSE:
                    (
                        record_date,
                        ex_date,
                        amount,
                        adjustment_amount,
                        total_shares,
                        participating_shares,
                    ) = _sse_distribution_terms(document_text)
                else:
                    date_section_match = _DISTRIBUTION_DATE_SECTION_PATTERN.search(document_text)
                    date_body = (
                        date_section_match.group("body") if date_section_match is not None else ""
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
                section_match = (
                    _IMPLEMENTATION_SECTION_PATTERN.search(document_text)
                    if not is_rights_issue
                    else None
                )
                if section_match is None and market is not MarketCode.SSE and not is_rights_issue:
                    raise ValueError(
                        "official corporate-action notice lacks implementation section"
                    )
                section_body = section_match.group("body") if section_match is not None else ""
                cash_term = _cash_term(section_body) if section_body else None
                cash_base = cash_term[0] if cash_term is not None else None
                if market is not MarketCode.SSE:
                    amount = (
                        _per_share_amount(
                            cash_term[1],
                            int(cash_term[0]),
                        )
                        if cash_term is not None
                        else None
                    )
                    adjustment_amount = amount
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
                        raise ValueError("official corporate-action share bases conflict")
                    share_base = next(iter(share_bases))
                    if cash_base is not None and share_base != cash_base:
                        raise ValueError("official corporate-action term bases conflict")
                    added_shares = sum(
                        (term[1] for term in share_terms),
                        Decimal(0),
                    )
                    share_ratio = Fraction(share_base + added_shares) / Fraction(share_base)
                if amount is None and share_ratio is None and rights_ratio is None:
                    raise ValueError("official corporate-action notice lacks supported terms")
                notices.append(
                    _ParsedNotice(
                        record_date=record_date,
                        ex_date=ex_date,
                        document=fetched_announcement.document,
                        distribution_cash_per_share=amount,
                        adjustment_cash_per_share=adjustment_amount,
                        total_shares=total_shares,
                        participating_shares=participating_shares,
                        share_ratio=share_ratio,
                        rights_ratio=rights_ratio,
                        rights_subscription_price=rights_subscription_price,
                        action_id=effective_announcement.action_id,
                        revision=effective_announcement.revision,
                    )
                )
            events: list[OfficialCorporateActionEvent] = []
            if notices:
                collected_at = self._clock()
                notices_by_ex_date: dict[date, list[_ParsedNotice]] = {}
                for notice in notices:
                    notices_by_ex_date.setdefault(notice.ex_date, []).append(notice)
                for ex_date, same_day in notices_by_ex_date.items():
                    record_dates = {notice.record_date for notice in same_day}
                    cash_values = {
                        notice.distribution_cash_per_share
                        for notice in same_day
                        if notice.distribution_cash_per_share is not None
                    }
                    adjustment_values = {
                        notice.adjustment_cash_per_share
                        for notice in same_day
                        if notice.adjustment_cash_per_share is not None
                    }
                    total_share_values = {
                        notice.total_shares
                        for notice in same_day
                        if notice.total_shares is not None
                    }
                    participating_share_values = {
                        notice.participating_shares
                        for notice in same_day
                        if notice.participating_shares is not None
                    }
                    share_ratios = {
                        notice.share_ratio for notice in same_day if notice.share_ratio is not None
                    }
                    rights_ratios = {
                        notice.rights_ratio
                        for notice in same_day
                        if notice.rights_ratio is not None
                    }
                    rights_prices = {
                        notice.rights_subscription_price
                        for notice in same_day
                        if notice.rights_subscription_price is not None
                    }
                    stable_action_ids = {
                        notice.action_id for notice in same_day if notice.action_id is not None
                    }
                    revisions = {notice.revision for notice in same_day}
                    if (
                        len(record_dates) != 1
                        or len(cash_values) > 1
                        or len(adjustment_values) > 1
                        or len(total_share_values) > 1
                        or len(participating_share_values) > 1
                        or len(share_ratios) > 1
                        or len(rights_ratios) > 1
                        or len(rights_prices) > 1
                        or len(stable_action_ids) > 1
                    ):
                        raise ValueError("official corporate-action notices conflict")
                    cash_value = next(iter(cash_values), None)
                    adjustment_value = next(iter(adjustment_values), None)
                    aggregate_share_ratio = next(iter(share_ratios), None)
                    aggregate_rights_ratio = next(iter(rights_ratios), None)
                    rights_price = next(iter(rights_prices), None)
                    component_count = sum(
                        (
                            cash_value is not None,
                            aggregate_share_ratio is not None,
                            aggregate_rights_ratio is not None,
                        )
                    )
                    if component_count >= 2:
                        action_kind: ActionKind = "composite"
                    elif aggregate_share_ratio is not None:
                        action_kind = "share_change"
                    elif aggregate_rights_ratio is not None:
                        action_kind = "rights_issue"
                    else:
                        action_kind = "cash_dividend"
                    events.append(
                        OfficialCorporateActionEvent(
                            action_id=next(
                                iter(stable_action_ids),
                                f"cninfo:{code}:{ex_date.isoformat()}",
                            ),
                            revision=max(revisions),
                            code=code,
                            market=market,
                            record_date=next(iter(record_dates)),
                            ex_date=ex_date,
                            action_kind=action_kind,
                            collected_at=collected_at,
                            source_id=CNINFO_CORPORATE_ACTION_SOURCE_ID,
                            upstream_id=CNINFO_CORPORATE_ACTION_UPSTREAM_ID,
                            parser_version=(CNINFO_CORPORATE_ACTION_PARSER_VERSION),
                            documents=tuple(notice.document for notice in same_day),
                            distribution_cash_per_share=cash_value,
                            adjustment_cash_per_share=adjustment_value,
                            total_shares=next(iter(total_share_values), None),
                            participating_shares=next(iter(participating_share_values), None),
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
                            rights_ratio_numerator=(
                                aggregate_rights_ratio.numerator
                                if aggregate_rights_ratio is not None
                                else None
                            ),
                            rights_ratio_denominator=(
                                aggregate_rights_ratio.denominator
                                if aggregate_rights_ratio is not None
                                else None
                            ),
                            rights_subscription_price=rights_price,
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
