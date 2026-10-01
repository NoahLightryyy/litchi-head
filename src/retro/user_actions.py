"""Immutable user-action ledger contracts.

The ledger records facts reported by a user.  It deliberately does not infer
portfolio P&L, fees, slippage, benchmark returns, or AI correctness.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class UserActionType(str, Enum):
    """Manual actions accepted during the compatibility migration."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    WATCH = "watch"
    IGNORE = "ignore"
    SKIP = "skip"


class AiSnapshotStatus(str, Enum):
    """Whether a referenced AI decision is eligible for later comparison."""

    UNVERIFIED = "unverified"
    LINKED = "linked"
    INVALID = "invalid"


class UserActionCreate(BaseModel):
    """Client-supplied facts for one manual action."""

    model_config = ConfigDict(extra="forbid")

    client_action_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    session_id: str = Field(min_length=1, max_length=128)
    stock_code: str = Field(pattern=r"^\d{6}$")
    action: UserActionType
    occurred_at: datetime
    quantity: Decimal | None = Field(default=None, gt=0)
    execution_price: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    stated_reason: str | None = Field(default=None, max_length=1000)
    reason_category: str | None = Field(default=None, max_length=100)
    ai_decision_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_event_facts(self) -> "UserActionCreate":
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must include timezone")
        if self.execution_price is not None and self.currency is None:
            raise ValueError("currency is required when execution_price is provided")
        if self.currency is not None and self.execution_price is None:
            raise ValueError("currency is only valid with execution_price")
        return self


class UserActionEvent(UserActionCreate):
    """Server-owned immutable ledger event."""

    schema_version: Literal["1"] = "1"
    event_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    recorded_at: datetime
    source: Literal["user_reported"] = "user_reported"
    ai_snapshot_status: AiSnapshotStatus = AiSnapshotStatus.UNVERIFIED
    limitations: list[str] = Field(
        default_factory=lambda: [
            "ai_snapshot_not_verified",
            "user_identity_not_authenticated",
        ]
    )


class UserActionWriteMeta(BaseModel):
    status: Literal["recorded", "replayed"]
    immutable: Literal[True] = True
    retry_mode: Literal["idempotent"] = "idempotent"


class UserActionWriteResponse(BaseModel):
    data: UserActionEvent
    meta: UserActionWriteMeta


class UserActionListMeta(BaseModel):
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    immutable: Literal[True] = True


class UserActionListResponse(BaseModel):
    data: list[UserActionEvent]
    meta: UserActionListMeta


class UserActionErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool


class UserActionErrorResponse(BaseModel):
    error: UserActionErrorBody


__all__ = [
    "AiSnapshotStatus",
    "UserActionCreate",
    "UserActionErrorResponse",
    "UserActionEvent",
    "UserActionListResponse",
    "UserActionListMeta",
    "UserActionType",
    "UserActionWriteMeta",
    "UserActionWriteResponse",
]
