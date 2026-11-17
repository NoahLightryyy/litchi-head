"""Automatic dated market observations, separate from historical verdicts and account P&L."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RetroObservation(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    record_id: str
    stock_code: str
    status: Literal["observed", "waiting", "unavailable", "not_found"]
    message: str
    recorded_date: date | None = None
    baseline_date: date | None = None
    latest_date: date | None = None
    baseline_price: float | None = Field(default=None, gt=0)
    latest_price: float | None = Field(default=None, gt=0)
    change_pct: float | None = None
    alignment: Literal["same", "opposite", "flat", "no_direction"] | None = None
    source: Literal["tencent"] = "tencent"
    price_basis: Literal["raw"] = "raw"
    baseline_method: Literal["first_available_close_on_or_after_record_date"] = (
        "first_available_close_on_or_after_record_date"
    )
    fetched_at: datetime | None = None


class RetroObservationsResponse(BaseModel):
    data: list[RetroObservation] = Field(max_length=10)
