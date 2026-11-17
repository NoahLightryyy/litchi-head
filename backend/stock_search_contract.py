"""Compatible stock search envelope, including bounded exact-code recovery."""
from typing import Literal

from pydantic import BaseModel, Field

from src.data.models import StockInfo


class StockSearchMeta(BaseModel):
    cached: bool = False
    latency_ms: int


class StockSearchResponse(BaseModel):
    data: list[StockInfo] = Field(max_length=20)
    meta: StockSearchMeta


class StockSearchErrorBody(BaseModel):
    code: Literal["STOCK_SEARCH_UNAVAILABLE"] = "STOCK_SEARCH_UNAVAILABLE"
    message: str = "股票搜索暂时没拿到数据，请用完整代码重试"


class StockSearchError(BaseModel):
    error: StockSearchErrorBody = Field(default_factory=StockSearchErrorBody)
