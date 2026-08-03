"""KR-2 source-agnostic corporate-action factors and point-in-time QFQ."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext
from fractions import Fraction
from hashlib import sha256
from math import prod
from typing import Literal
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from src.data.kline import MarketCode, RawDailyBar, market_code_for

ActionKind = Literal[
    "cash_dividend",
    "share_change",
    "rights_issue",
    "split",
    "reverse_split",
    "composite",
]
CorporateActionRevisionStatus = Literal[
    "active",
    "corrected",
    "supplemented",
    "delayed",
    "terminated",
    "cancelled",
    "changed",
    "adjusted",
]

A_SHARE_SECURITY_CODE_PATTERN = re.compile(
    r"(?:00[0-3]\d{3}|30[01]\d{3}|60[0135]\d{3}|68[89]\d{3}|[48]\d{5}|92\d{4})"
)


def is_supported_a_share_code(code: str) -> bool:
    """Return whether a code belongs to an explicitly supported A-share board."""

    return A_SHARE_SECURITY_CODE_PATTERN.fullmatch(code) is not None


def _decimal_precision(value: Decimal) -> Decimal:
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):
        raise ValueError("decimal precision requires a finite value")
    return Decimal(1).scaleb(exponent)


class AdjustedDailyBar(BaseModel):
    """One derived qfq daily bar that must never masquerade as a RAW price."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=6, max_length=6)
    market: MarketCode
    trade_date: date
    period: Literal["1d"] = "1d"
    currency: Literal["CNY"] = "CNY"
    price_basis: Literal["adjusted_qfq_asof"] = "adjusted_qfq_asof"
    volume_basis: Literal["adjusted_qfq_asof"] = "adjusted_qfq_asof"
    amount_basis: Literal["raw"] = "raw"
    open: Decimal = Field(ge=0)
    high: Decimal = Field(ge=0)
    low: Decimal = Field(ge=0)
    close: Decimal = Field(ge=0)
    volume: Decimal = Field(ge=0)
    amount: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_ohlc(self) -> "AdjustedDailyBar":
        if self.high < self.low:
            raise ValueError("high must be greater than or equal to low")
        if not self.low <= self.open <= self.high:
            raise ValueError("open must be within the daily low/high range")
        if not self.low <= self.close <= self.high:
            raise ValueError("close must be within the daily low/high range")
        return self


class CorporateActionFactor(BaseModel):
    """One versioned factor backed by an independent corporate-action source."""

    model_config = ConfigDict(frozen=True)

    action_id: str = Field(min_length=1)
    code: str = Field(min_length=6, max_length=6)
    market: MarketCode
    ex_date: date
    action_kind: ActionKind
    known_at: datetime
    price_factor: Decimal = Field(gt=0)
    volume_factor: Decimal = Field(gt=0)
    price_factor_precision: Decimal = Field(gt=0)
    volume_factor_precision: Decimal = Field(gt=0)
    share_ratio_numerator: int | None = Field(default=None, gt=0)
    share_ratio_denominator: int | None = Field(default=None, gt=0)
    factor_source_ids: tuple[str, ...] = Field(min_length=1)
    factor_upstream_ids: tuple[str, ...] = Field(min_length=1)
    verification_source_ids: tuple[str, ...] = Field(min_length=1)
    verification_upstream_ids: tuple[str, ...] = Field(min_length=1)
    factor_version: str = Field(min_length=1)
    revision: int = Field(ge=1, strict=True)

    @field_validator("action_id", "factor_version")
    @classmethod
    def validate_identity(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("factor identities must be non-blank")
        return normalized

    @field_validator("known_at")
    @classmethod
    def validate_known_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("known_at must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator(
        "factor_source_ids",
        "factor_upstream_ids",
        "verification_source_ids",
        "verification_upstream_ids",
    )
    @classmethod
    def validate_provenance(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("factor provenance identifiers must be non-blank")
        return tuple(sorted({value.strip() for value in values}))

    @model_validator(mode="after")
    def validate_factor(self) -> "CorporateActionFactor":
        if set(self.factor_upstream_ids) & set(self.verification_upstream_ids):
            raise ValueError(
                "factor and corporate-action verification require independent upstreams"
            )
        if self.action_kind == "cash_dividend" and self.volume_factor != Decimal("1"):
            raise ValueError("cash dividend must preserve RAW volume")
        has_share_ratio = (
            self.share_ratio_numerator is not None and self.share_ratio_denominator is not None
        )
        if (self.share_ratio_numerator is None) != (self.share_ratio_denominator is None):
            raise ValueError("share ratio numerator and denominator must appear together")
        requires_share_ratio = self.action_kind in {
            "share_change",
            "split",
            "reverse_split",
            "rights_issue",
        } or (self.action_kind == "composite" and self.volume_factor != Decimal("1"))
        if requires_share_ratio and not has_share_ratio:
            raise ValueError("share-count actions require an exact share ratio")
        if self.action_kind == "cash_dividend" and has_share_ratio:
            raise ValueError("cash dividend cannot carry a share ratio")
        if has_share_ratio:
            assert self.share_ratio_numerator is not None
            assert self.share_ratio_denominator is not None
            expected_volume = Fraction(
                self.share_ratio_numerator,
                self.share_ratio_denominator,
            )
            volume_error = abs(Fraction(self.volume_factor) - expected_volume)
            if volume_error > Fraction(self.volume_factor_precision) / 2:
                raise ValueError("volume factor conflicts with the exact share ratio")
            if self.action_kind in {"share_change", "split", "reverse_split"}:
                expected_price = 1 / expected_volume
                price_error = abs(Fraction(self.price_factor) - expected_price)
                if price_error > Fraction(self.price_factor_precision) / 2:
                    raise ValueError("price factor conflicts with the exact share ratio")
        return self


class OfficialCorporateActionDocument(BaseModel):
    """One content-addressed official document supporting an action event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    external_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    published_at: datetime
    source_url: str = Field(min_length=1)
    attachment_url: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("external_id", "title")
    @classmethod
    def validate_identity(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("official document identity must be non-blank")
        return normalized

    @field_validator("source_url", "attachment_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        normalized = value.strip()
        parsed = urlparse(normalized)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("official document URLs must be valid HTTPS URLs")
        return normalized

    @field_validator("published_at")
    @classmethod
    def validate_published_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("published_at must be timezone-aware")
        return value.astimezone(UTC)


class OfficialCorporateActionRevision(BaseModel):
    """One immutable transition in an official corporate-action document chain."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    revision: int = Field(ge=1, strict=True)
    status: CorporateActionRevisionStatus
    document: OfficialCorporateActionDocument
    supersedes_document_ids: tuple[str, ...] = ()

    @field_validator("supersedes_document_ids")
    @classmethod
    def validate_supersedes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(value.strip() for value in values)
        if any(not value for value in normalized) or len(set(normalized)) != len(normalized):
            raise ValueError("superseded document identities must be unique and non-blank")
        return tuple(sorted(normalized))

    @model_validator(mode="after")
    def validate_transition_shape(self) -> "OfficialCorporateActionRevision":
        if self.revision == 1:
            if self.status != "active" or self.supersedes_document_ids:
                raise ValueError("first corporate-action revision must be active")
        elif self.status == "active" or not self.supersedes_document_ids:
            raise ValueError("later corporate-action revisions must supersede prior documents")
        if self.document.external_id in self.supersedes_document_ids:
            raise ValueError("corporate-action revision cannot supersede itself")
        return self


class CorporateActionRevisionLedger(BaseModel):
    """Ordered official revisions whose effective set gates event generation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(min_length=6, max_length=6)
    market: MarketCode
    revisions: tuple[OfficialCorporateActionRevision, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_chain(self) -> "CorporateActionRevisionLedger":
        if not is_supported_a_share_code(self.code) or self.market is not market_code_for(
            self.code
        ):
            raise ValueError("revision ledger code and market do not match")
        ordered = tuple(sorted(self.revisions, key=lambda item: item.revision))
        if tuple(item.revision for item in ordered) != tuple(range(1, len(ordered) + 1)):
            raise ValueError("corporate-action revisions must be contiguous and unique")
        known: set[str] = set()
        for revision in ordered:
            if any(item not in known for item in revision.supersedes_document_ids):
                raise ValueError("corporate-action revision supersedes an unknown document")
            if revision.document.external_id in known:
                raise ValueError("corporate-action revision document identity is duplicated")
            known.add(revision.document.external_id)
        object.__setattr__(self, "revisions", ordered)
        return self

    @property
    def effective_documents(self) -> tuple[OfficialCorporateActionDocument, ...]:
        effective: dict[str, OfficialCorporateActionDocument] = {}
        for revision in self.revisions:
            for external_id in revision.supersedes_document_ids:
                effective.pop(external_id, None)
            if revision.status in {"active", "corrected", "supplemented", "changed", "adjusted"}:
                effective[revision.document.external_id] = revision.document
        return tuple(
            sorted(
                effective.values(),
                key=lambda document: (document.published_at, document.external_id),
            )
        )

    @property
    def can_generate_event(self) -> bool:
        return bool(self.effective_documents) and self.revisions[-1].status not in {
            "delayed",
            "terminated",
            "cancelled",
        }


class OfficialCorporateActionEvent(BaseModel):
    """Official terms that may verify, but do not themselves supply, a factor."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_id: str = Field(min_length=1)
    revision: int = Field(ge=1, strict=True)
    code: str = Field(min_length=6, max_length=6)
    market: MarketCode
    record_date: date
    ex_date: date
    action_kind: ActionKind
    collected_at: datetime
    source_id: str = Field(min_length=1)
    upstream_id: str = Field(min_length=1)
    parser_version: str = Field(min_length=1)
    documents: tuple[OfficialCorporateActionDocument, ...] = Field(min_length=1)
    cash_dividend_per_share: Decimal | None = Field(
        default=None,
        gt=0,
        strict=True,
    )
    distribution_cash_per_share: Decimal | None = Field(
        default=None,
        gt=0,
        strict=True,
    )
    adjustment_cash_per_share: Decimal | None = Field(
        default=None,
        gt=0,
        strict=True,
    )
    total_shares: int | None = Field(default=None, gt=0, strict=True)
    participating_shares: int | None = Field(default=None, gt=0, strict=True)
    share_ratio_numerator: int | None = Field(
        default=None,
        gt=0,
        strict=True,
    )
    share_ratio_denominator: int | None = Field(
        default=None,
        gt=0,
        strict=True,
    )
    rights_ratio_numerator: int | None = Field(
        default=None,
        gt=0,
        strict=True,
    )
    rights_ratio_denominator: int | None = Field(
        default=None,
        gt=0,
        strict=True,
    )
    rights_subscription_price: Decimal | None = Field(
        default=None,
        gt=0,
        strict=True,
    )

    @model_validator(mode="before")
    @classmethod
    def migrate_cash_basis(cls, value: object, info: ValidationInfo) -> object:
        if not isinstance(value, dict):
            return value
        migrated = dict(value)
        if info.mode == "json":
            for field_name in (
                "cash_dividend_per_share",
                "distribution_cash_per_share",
                "adjustment_cash_per_share",
            ):
                raw = migrated.get(field_name)
                if isinstance(raw, str):
                    migrated[field_name] = Decimal(raw)
        legacy = migrated.get("cash_dividend_per_share")
        distribution = migrated.get("distribution_cash_per_share")
        if legacy is not None and distribution is not None and legacy != distribution:
            raise ValueError("cash_dividend_per_share conflicts with distribution_cash_per_share")
        if distribution is None and legacy is not None:
            migrated["distribution_cash_per_share"] = legacy
            distribution = legacy
        if legacy is None and distribution is not None:
            migrated["cash_dividend_per_share"] = distribution
        if migrated.get("adjustment_cash_per_share") is None and distribution is not None:
            migrated["adjustment_cash_per_share"] = distribution
        return migrated

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        if not is_supported_a_share_code(value):
            raise ValueError("code must be an explicitly supported A-share code")
        return value

    @field_validator("action_id", "source_id", "upstream_id", "parser_version")
    @classmethod
    def validate_identity(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("official action identity must be non-blank")
        return normalized

    @field_validator("collected_at")
    @classmethod
    def validate_collected_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("collected_at must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("documents")
    @classmethod
    def validate_documents(
        cls,
        values: tuple[OfficialCorporateActionDocument, ...],
    ) -> tuple[OfficialCorporateActionDocument, ...]:
        external_ids = tuple(document.external_id for document in values)
        content_hashes = tuple(document.content_hash for document in values)
        if len(set(external_ids)) != len(external_ids):
            raise ValueError("official action documents contain duplicate external_id")
        if len(set(content_hashes)) != len(content_hashes):
            raise ValueError("official action documents contain duplicate content_hash")
        return tuple(
            sorted(
                values,
                key=lambda document: (
                    document.published_at,
                    document.external_id,
                    document.content_hash,
                ),
            )
        )

    @model_validator(mode="after")
    def validate_instrument(self) -> "OfficialCorporateActionEvent":
        if self.market is not market_code_for(self.code):
            raise ValueError("official action code and market do not match")
        if self.record_date >= self.ex_date:
            raise ValueError("record_date must be earlier than ex_date")
        if any(document.published_at > self.collected_at for document in self.documents):
            raise ValueError("document published_at must not be later than collected_at")
        share_values = (
            self.share_ratio_numerator,
            self.share_ratio_denominator,
        )
        rights_values = (
            self.rights_ratio_numerator,
            self.rights_ratio_denominator,
        )
        has_share_values = any(value is not None for value in share_values)
        has_share_ratio = all(value is not None for value in share_values)
        has_rights_values = any(value is not None for value in rights_values)
        has_rights_ratio = all(value is not None for value in rights_values)
        has_rights_terms = has_rights_ratio and (self.rights_subscription_price is not None)
        has_any_rights_term = has_rights_values or self.rights_subscription_price is not None
        has_cash = self.distribution_cash_per_share is not None
        cash_values = (
            self.cash_dividend_per_share,
            self.distribution_cash_per_share,
            self.adjustment_cash_per_share,
        )
        if any(value is None for value in cash_values) != all(
            value is None for value in cash_values
        ):
            raise ValueError("cash distribution and adjustment basis must appear together")
        if (
            self.cash_dividend_per_share is not None
            and self.cash_dividend_per_share != self.distribution_cash_per_share
        ):
            raise ValueError("legacy cash basis must equal distribution cash basis")
        has_total_shares = self.total_shares is not None
        has_participating_shares = self.participating_shares is not None
        if has_total_shares != has_participating_shares:
            raise ValueError("total_shares and participating_shares must appear together")
        if has_total_shares:
            assert self.total_shares is not None
            assert self.participating_shares is not None
            if self.participating_shares > self.total_shares:
                raise ValueError("participating_shares must not exceed total_shares")
        if (
            self.distribution_cash_per_share != self.adjustment_cash_per_share
            and not has_total_shares
        ):
            raise ValueError(
                "differential cash adjustment requires total_shares and participating_shares"
            )

        share_increase = False
        share_decrease = False
        if has_share_ratio:
            assert self.share_ratio_numerator is not None
            assert self.share_ratio_denominator is not None
            share_increase = self.share_ratio_numerator > self.share_ratio_denominator
            share_decrease = self.share_ratio_numerator < self.share_ratio_denominator
        terms_valid = False
        if self.action_kind == "cash_dividend":
            terms_valid = has_cash and not has_share_values and not has_any_rights_term
        elif self.action_kind == "share_change":
            terms_valid = share_increase and not has_cash and not has_any_rights_term
        elif self.action_kind == "split":
            terms_valid = share_increase and not has_cash and not has_any_rights_term
        elif self.action_kind == "reverse_split":
            terms_valid = share_decrease and not has_cash and not has_any_rights_term
        elif self.action_kind == "rights_issue":
            terms_valid = has_rights_terms and not has_cash and not has_share_values
        elif self.action_kind == "composite":
            component_count = sum(
                (
                    has_cash,
                    share_increase or share_decrease,
                    has_rights_terms,
                )
            )
            terms_valid = component_count >= 2

        if (
            not terms_valid
            or has_share_values != has_share_ratio
            or has_rights_values != has_rights_ratio
            or (has_any_rights_term and not has_rights_terms)
            or (has_share_ratio and not share_increase and not share_decrease)
        ):
            raise ValueError("official action terms are incompatible with action_kind")
        return self


class CumulativeQfqFactorPoint(BaseModel):
    """One dated divisor from a versioned upstream QFQ-factor snapshot."""

    model_config = ConfigDict(frozen=True)

    effective_date: date
    cumulative_divisor: Decimal = Field(gt=0)
    precision: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def validate_precision(self) -> "CumulativeQfqFactorPoint":
        if self.precision != _decimal_precision(self.cumulative_divisor):
            raise ValueError("precision must match the cumulative divisor decimal exponent")
        return self


class QfqFactorSnapshot(BaseModel):
    """An immutable, content-addressed cumulative QFQ-factor response."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=6, max_length=6)
    market: MarketCode
    source_id: str = Field(min_length=1)
    upstream_id: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    collected_at: datetime
    response_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_bytes: int = Field(gt=0)
    factor_version: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    base_divisor: Decimal = Field(gt=0)
    base_precision: Decimal = Field(gt=0)
    points: tuple[CumulativeQfqFactorPoint, ...]

    @field_validator("source_id", "upstream_id", "adapter_version")
    @classmethod
    def validate_snapshot_identity(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("QFQ snapshot identities must be non-blank")
        return normalized

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        if not is_supported_a_share_code(value):
            raise ValueError("code must be an explicitly supported A-share code")
        return value

    @field_validator("collected_at")
    @classmethod
    def validate_collected_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("collected_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_snapshot_consistency(self) -> "QfqFactorSnapshot":
        if self.market is not market_code_for(self.code):
            raise ValueError("QFQ snapshot code and market do not match")
        if self.factor_version != f"sha256:{self.response_hash}":
            raise ValueError("factor_version must identify the response hash")
        if self.base_precision != _decimal_precision(self.base_divisor):
            raise ValueError("base_precision must match the base divisor decimal exponent")
        dates = tuple(point.effective_date for point in self.points)
        if dates != tuple(sorted(set(dates))):
            raise ValueError("QFQ factor points must be unique and ordered")
        if not self.points:
            if self.base_divisor != Decimal("1"):
                raise ValueError("empty QFQ history requires a unit base divisor")
            return self
        if self.points[0].cumulative_divisor != self.base_divisor:
            raise ValueError("QFQ base divisor must equal the oldest factor point")
        if self.points[0].precision != self.base_precision:
            raise ValueError("QFQ base precision must equal the oldest point precision")
        if self.points[-1].cumulative_divisor != Decimal("1"):
            raise ValueError("latest QFQ factor point must be anchored at one")
        return self


class AdjustedKlineSeries(BaseModel):
    """A deterministic qfq series plus the factor lineage used to derive it."""

    model_config = ConfigDict(frozen=True)

    adjustment_mode: Literal["qfq"] = "qfq"
    raw_snapshot_id: str = Field(min_length=1)
    factor_source_ids: tuple[str, ...]
    factor_version: str = Field(min_length=1)
    reference_date: date
    raw_snapshot_as_of: datetime
    raw_completed_through: date
    as_of: datetime
    bars: tuple[AdjustedDailyBar, ...]

    @field_validator("raw_snapshot_id", "factor_version")
    @classmethod
    def validate_series_identity(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("adjustment series identities must be non-blank")
        return normalized

    @field_validator("factor_source_ids")
    @classmethod
    def validate_factor_sources(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("factor source identifiers must be non-blank")
        return tuple(sorted({value.strip() for value in values}))

    @field_validator("raw_snapshot_as_of", "as_of")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("adjustment timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_order(self) -> "AdjustedKlineSeries":
        if self.raw_snapshot_as_of > self.as_of:
            raise ValueError("RAW snapshot newer than as_of is not allowed")
        if self.raw_completed_through > self.raw_snapshot_as_of.date():
            raise ValueError("RAW completion proof postdates the snapshot")
        if (self.factor_version == "none") != (not self.factor_source_ids):
            raise ValueError("factor_version none and empty factor sources must appear together")
        if not self.bars:
            raise ValueError("adjusted series requires bars")
        identity = {(bar.code, bar.market) for bar in self.bars}
        if len(identity) != 1:
            raise ValueError("adjusted series requires one instrument")
        dates = tuple(bar.trade_date for bar in self.bars)
        if dates != tuple(sorted(set(dates))):
            raise ValueError("adjusted series dates must be unique and ordered")
        if self.reference_date != dates[-1]:
            raise ValueError("reference_date must equal the last adjusted bar date")
        if dates[-1] > self.raw_completed_through:
            raise ValueError("adjusted bars exceed the snapshot completion proof")
        return self


def _selected_factor_revisions(
    factors: tuple[CorporateActionFactor, ...],
    *,
    as_of: datetime,
    code: str,
    market: MarketCode,
    reference_date: date,
) -> tuple[CorporateActionFactor, ...]:
    eligible = [
        factor
        for factor in factors
        if factor.known_at <= as_of and factor.ex_date <= reference_date
    ]
    selected: dict[str, CorporateActionFactor] = {}
    for factor in eligible:
        if factor.code != code or factor.market != market:
            raise ValueError("corporate-action factor instrument does not match RAW bars")
        current = selected.get(factor.action_id)
        if current is not None and factor.revision == current.revision and factor != current:
            raise ValueError("conflicting factor revision for corporate action")
        if current is None or (factor.revision, factor.known_at, factor.factor_version) > (
            current.revision,
            current.known_at,
            current.factor_version,
        ):
            selected[factor.action_id] = factor
    return tuple(
        sorted(
            selected.values(),
            key=lambda factor: (
                factor.ex_date,
                factor.action_id,
                factor.revision,
                factor.factor_version,
            ),
        )
    )


def _factor_set_version(factors: tuple[CorporateActionFactor, ...]) -> str:
    if not factors:
        return "none"
    canonical_content = json.dumps(
        [factor.model_dump(mode="json") for factor in factors],
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"sha256:{sha256(canonical_content.encode('utf-8')).hexdigest()}"


def adjust_qfq_as_of(
    raw_bars: Iterable[RawDailyBar],
    factors: Iterable[CorporateActionFactor],
    *,
    raw_snapshot_id: str,
    raw_snapshot_as_of: datetime,
    raw_completed_through: date,
    as_of: datetime,
) -> AdjustedKlineSeries:
    """Derive a qfq series using only factor evidence known by ``as_of``."""

    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    if raw_snapshot_as_of.tzinfo is None or raw_snapshot_as_of.utcoffset() is None:
        raise ValueError("raw_snapshot_as_of must be timezone-aware")
    as_of_utc = as_of.astimezone(UTC)
    raw_snapshot_as_of_utc = raw_snapshot_as_of.astimezone(UTC)
    if raw_snapshot_as_of_utc > as_of_utc:
        raise ValueError("RAW snapshot newer than as_of is not allowed")
    if not raw_snapshot_id.strip():
        raise ValueError("raw_snapshot_id must be non-blank")
    bars = tuple(sorted(raw_bars, key=lambda bar: bar.trade_date))
    if not bars:
        raise ValueError("qfq adjustment requires RAW bars")
    if len({bar.trade_date for bar in bars}) != len(bars):
        raise ValueError("qfq adjustment requires unique RAW trade dates")
    code = bars[0].code
    market = bars[0].market
    if any(bar.code != code or bar.market != market for bar in bars):
        raise ValueError("qfq adjustment requires one RAW instrument")
    if any(bar.trade_date > raw_completed_through for bar in bars):
        raise ValueError("RAW bars exceed the snapshot completion proof")
    if raw_completed_through > raw_snapshot_as_of_utc.date():
        raise ValueError("RAW completion proof postdates the snapshot")
    reference_date = bars[-1].trade_date
    selected = _selected_factor_revisions(
        tuple(CorporateActionFactor.model_validate(factor.model_dump()) for factor in factors),
        as_of=as_of_utc,
        code=code,
        market=market,
        reference_date=reference_date,
    )
    max_price_digits = max(
        len(value.as_tuple().digits)
        for bar in bars
        for value in (bar.open, bar.high, bar.low, bar.close)
    )
    max_volume_digits = max(len(Decimal(bar.volume).as_tuple().digits) for bar in bars)
    calculation_precision = max(
        28,
        max_price_digits + sum(len(factor.price_factor.as_tuple().digits) for factor in selected),
        max_volume_digits + sum(len(factor.volume_factor.as_tuple().digits) for factor in selected),
    )
    adjusted_items: list[AdjustedDailyBar] = []
    with localcontext() as context:
        context.prec = calculation_precision
        for bar in bars:
            applicable = tuple(factor for factor in selected if bar.trade_date < factor.ex_date)
            price_multiplier = prod(
                (factor.price_factor for factor in applicable),
                start=Decimal("1"),
            )
            volume_multiplier = prod(
                (factor.volume_factor for factor in applicable),
                start=Decimal("1"),
            )
            adjusted_items.append(
                AdjustedDailyBar(
                    code=bar.code,
                    market=bar.market,
                    trade_date=bar.trade_date,
                    open=bar.open * price_multiplier,
                    high=bar.high * price_multiplier,
                    low=bar.low * price_multiplier,
                    close=bar.close * price_multiplier,
                    volume=Decimal(bar.volume) * volume_multiplier,
                    amount=bar.amount,
                )
            )
    adjusted = tuple(adjusted_items)
    return AdjustedKlineSeries(
        raw_snapshot_id=raw_snapshot_id.strip(),
        factor_source_ids=tuple(
            sorted({source_id for factor in selected for source_id in factor.factor_source_ids})
        ),
        factor_version=_factor_set_version(selected),
        reference_date=reference_date,
        raw_snapshot_as_of=raw_snapshot_as_of_utc,
        raw_completed_through=raw_completed_through,
        as_of=as_of_utc,
        bars=adjusted,
    )


__all__ = [
    "ActionKind",
    "AdjustedDailyBar",
    "AdjustedKlineSeries",
    "CorporateActionFactor",
    "CorporateActionRevisionLedger",
    "CorporateActionRevisionStatus",
    "CumulativeQfqFactorPoint",
    "OfficialCorporateActionDocument",
    "OfficialCorporateActionEvent",
    "OfficialCorporateActionRevision",
    "QfqFactorSnapshot",
    "adjust_qfq_as_of",
    "is_supported_a_share_code",
]
