"""KR-2B-2 official corporate-action evidence contracts."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from src.data.kline import MarketCode
from src.data.kline_adjustment import (
    OfficialCorporateActionDocument,
    OfficialCorporateActionEvent,
)


def _document(**changes: Any) -> OfficialCorporateActionDocument:
    values: dict[str, Any] = {
        "external_id": "1225352449",
        "title": "2025年年度权益分派实施公告",
        "published_at": datetime(2026, 6, 5, 0, 0, tzinfo=UTC),
        "source_url": (
            "https://www.cninfo.com.cn/new/disclosure/detail"
            "?stockCode=000001&announcementId=1225352449"
        ),
        "attachment_url": (
            "https://static.cninfo.com.cn/"
            "finalpage/2026-06-05/1225352449.PDF"
        ),
        "content_hash": "8" * 64,
    }
    values.update(changes)
    return OfficialCorporateActionDocument(**values)


def _event(**changes: Any) -> OfficialCorporateActionEvent:
    values: dict[str, Any] = {
        "action_id": "000001:2026-06-12:cash-dividend",
        "revision": 1,
        "code": "000001",
        "market": MarketCode.SZSE,
        "record_date": date(2026, 6, 11),
        "ex_date": date(2026, 6, 12),
        "action_kind": "cash_dividend",
        "collected_at": datetime(2026, 6, 12, 1, 0, tzinfo=UTC),
        "source_id": "cninfo-corporate-action",
        "upstream_id": "cninfo",
        "parser_version": "cninfo-corporate-action-v1",
        "documents": (_document(),),
        "cash_dividend_per_share": Decimal("0.236"),
    }
    values.update(changes)
    return OfficialCorporateActionEvent(**values)


def test_cash_dividend_event_preserves_official_document_and_terms() -> None:
    event = _event()

    assert event.action_kind == "cash_dividend"
    assert event.cash_dividend_per_share == Decimal("0.236")
    assert event.share_ratio_numerator is None
    assert event.rights_ratio_numerator is None
    assert event.documents[0].external_id == "1225352449"
    assert event.parser_version == "cninfo-corporate-action-v1"
    assert OfficialCorporateActionEvent.model_validate_json(
        event.model_dump_json()
    ) == event


@pytest.mark.parametrize(
    ("code", "market"),
    [
        ("ABCDEF", MarketCode.SZSE),
        ("600000", MarketCode.SZSE),
    ],
)
def test_official_action_rejects_invalid_instrument_identity(
    code: str,
    market: MarketCode,
) -> None:
    with pytest.raises(ValidationError, match="code|market"):
        _event(code=code, market=market)


def test_official_action_rejects_impossible_point_in_time_relationships() -> None:
    with pytest.raises(ValidationError, match="record_date"):
        _event(record_date=date(2026, 6, 12))

    with pytest.raises(ValidationError, match="published_at"):
        _event(
            documents=(
                _document(
                    published_at=datetime(2026, 6, 13, 0, 0, tzinfo=UTC)
                ),
            )
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"cash_dividend_per_share": None},
        {
            "share_ratio_numerator": 3,
            "share_ratio_denominator": 2,
        },
        {
            "action_kind": "share_change",
            "cash_dividend_per_share": None,
        },
        {
            "action_kind": "share_change",
            "cash_dividend_per_share": None,
            "share_ratio_numerator": 1,
            "share_ratio_denominator": 1,
        },
        {
            "action_kind": "split",
            "cash_dividend_per_share": None,
            "share_ratio_numerator": 1,
            "share_ratio_denominator": 2,
        },
        {
            "action_kind": "reverse_split",
            "cash_dividend_per_share": None,
            "share_ratio_numerator": 3,
            "share_ratio_denominator": 2,
        },
        {
            "action_kind": "rights_issue",
            "cash_dividend_per_share": None,
        },
        {
            "action_kind": "rights_issue",
            "cash_dividend_per_share": None,
            "rights_ratio_numerator": 3,
            "rights_ratio_denominator": 10,
        },
        {
            "action_kind": "composite",
        },
        {
            "action_kind": "composite",
            "share_ratio_numerator": 3,
            "share_ratio_denominator": 2,
            "rights_ratio_numerator": 1,
            "rights_ratio_denominator": 10,
        },
        {
            "action_kind": "composite",
            "share_ratio_numerator": 1,
            "share_ratio_denominator": 1,
            "rights_ratio_numerator": 1,
            "rights_ratio_denominator": 10,
            "rights_subscription_price": Decimal("7.50"),
        },
    ],
)
def test_official_action_rejects_terms_incompatible_with_kind(
    changes: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError, match="terms"):
        _event(**changes)


def test_official_action_documents_are_unique_and_canonically_ordered() -> None:
    later_document = _document(
        external_id="1225352450",
        content_hash="9" * 64,
    )

    event = _event(documents=(later_document, _document()))

    assert [document.external_id for document in event.documents] == [
        "1225352449",
        "1225352450",
    ]
    with pytest.raises(ValidationError, match="duplicate"):
        _event(
            documents=(
                _document(),
                _document(content_hash="9" * 64),
            )
        )
    with pytest.raises(ValidationError, match="duplicate"):
        _event(
            documents=(
                _document(),
                _document(
                    external_id="1225352450",
                ),
            )
        )


@pytest.mark.parametrize(
    "document_changes",
    [
        {"external_id": "   "},
        {"title": "   "},
        {"source_url": "http://www.cninfo.com.cn/detail"},
        {"attachment_url": "file:///tmp/action.pdf"},
        {"source_url": "https://"},
        {"attachment_url": "https://\n"},
    ],
)
def test_official_document_rejects_blank_identity_or_non_https_url(
    document_changes: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError, match="blank|HTTPS"):
        _document(**document_changes)


@pytest.mark.parametrize(
    "event_changes",
    [
        {"action_id": "   "},
        {"source_id": "   "},
        {"upstream_id": "   "},
        {"parser_version": "   "},
    ],
)
def test_official_action_rejects_blank_provenance(
    event_changes: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError, match="blank"):
        _event(**event_changes)


def test_share_change_preserves_exact_post_to_pre_share_ratio() -> None:
    event = _event(
        action_kind="share_change",
        cash_dividend_per_share=None,
        share_ratio_numerator=3,
        share_ratio_denominator=2,
    )

    assert (
        event.share_ratio_numerator,
        event.share_ratio_denominator,
    ) == (3, 2)


@pytest.mark.parametrize(
    ("action_kind", "numerator", "denominator"),
    [
        ("split", 3, 1),
        ("reverse_split", 1, 3),
    ],
)
def test_split_terms_preserve_their_exact_share_direction(
    action_kind: str,
    numerator: int,
    denominator: int,
) -> None:
    event = _event(
        action_kind=action_kind,
        cash_dividend_per_share=None,
        share_ratio_numerator=numerator,
        share_ratio_denominator=denominator,
    )

    assert (
        event.share_ratio_numerator,
        event.share_ratio_denominator,
    ) == (numerator, denominator)


def test_rights_issue_preserves_exact_ratio_and_subscription_price() -> None:
    event = _event(
        action_kind="rights_issue",
        cash_dividend_per_share=None,
        rights_ratio_numerator=3,
        rights_ratio_denominator=10,
        rights_subscription_price=Decimal("8.25"),
    )

    assert (
        event.rights_ratio_numerator,
        event.rights_ratio_denominator,
        event.rights_subscription_price,
    ) == (3, 10, Decimal("8.25"))


def test_composite_event_requires_and_preserves_multiple_term_components() -> None:
    event = _event(
        action_kind="composite",
        share_ratio_numerator=3,
        share_ratio_denominator=2,
        rights_ratio_numerator=1,
        rights_ratio_denominator=10,
        rights_subscription_price=Decimal("7.50"),
    )

    assert event.cash_dividend_per_share == Decimal("0.236")
    assert (
        event.share_ratio_numerator,
        event.share_ratio_denominator,
    ) == (3, 2)
    assert (
        event.rights_ratio_numerator,
        event.rights_ratio_denominator,
        event.rights_subscription_price,
    ) == (1, 10, Decimal("7.50"))


@pytest.mark.parametrize(
    "changes",
    [
        {"cash_dividend_per_share": 0.236},
        {"revision": "1"},
        {"revision": 1.0},
        {"revision": True},
        {
            "action_kind": "share_change",
            "cash_dividend_per_share": None,
            "share_ratio_numerator": 3.0,
            "share_ratio_denominator": 2,
        },
        {
            "action_kind": "rights_issue",
            "cash_dividend_per_share": None,
            "rights_ratio_numerator": 3,
            "rights_ratio_denominator": 10,
            "rights_subscription_price": 8.25,
        },
    ],
)
def test_official_action_terms_reject_implicit_numeric_coercion(
    changes: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        _event(**changes)


def test_official_action_models_reject_unknown_schema_fields() -> None:
    document_data = _document().model_dump()
    document_data["unexpected_field"] = "schema drift"
    with pytest.raises(ValidationError, match="extra"):
        OfficialCorporateActionDocument.model_validate(document_data)

    event_data = _event().model_dump()
    event_data["unexpected_field"] = "schema drift"
    with pytest.raises(ValidationError, match="extra"):
        OfficialCorporateActionEvent.model_validate(event_data)
