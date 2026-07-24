"""PD 动态指标选择器 —— 股票 → 行业 → 产业链位置 → 关键指标

组合 IndicatorRegistry + 产业链位置 + DataSource 完成全链路：
    stock_code → get_stock_industry() → normalize → classify_chain_position()
    → REGISTRY lookup → SelectorResult
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from src.data.indicators.registry import (
    INDICATOR_DEFS_MAP,
    REGISTRY,
    IndicatorDef,
    IndustryChainPosition,
    classify_chain_position,
    normalize_industry,
)
from src.data.providers.base import DataSource

logger = logging.getLogger("data.indicators.selector")


class SelectorResult(BaseModel):
    """动态指标选择结果

    对一只股票，输出其所属行业、产业链位置和关键指标列表。
    """

    stock_code: str
    industry: str = ""
    chain_position: IndustryChainPosition = IndustryChainPosition.OTHER
    indicator_ids: list[str] = Field(default_factory=list)
    indicator_defs: list[IndicatorDef] = Field(default_factory=list)


class DynamicIndicatorSelector:
    """动态指标选择器

    组合股票→行业→产业链位置→关键指标的全链路。

    Args:
        source: DataSource 实现（用于调用 get_stock_industry）
    """

    def __init__(self, source: DataSource) -> None:
        self._source = source

    def for_stock(self, code: str) -> SelectorResult:
        """获取个股的动态关键指标

        Args:
            code: 股票代码，如 "000001"

        Returns:
            包含行业、产业链位置和关键指标的 SelectorResult
        """
        # 1. 获取原始行业名
        raw = self._get_industry_raw(code)
        if not raw:
            return SelectorResult(stock_code=code)

        # 2. 归一化到一级行业
        industry = normalize_industry(raw)
        if not industry or industry not in REGISTRY:
            logger.warning("行业 '%s' (raw='%s') 未在注册表中", industry, raw)
            return SelectorResult(stock_code=code, industry=industry)

        # 3. 产业链位置
        position = classify_chain_position(industry)

        # 4. 查注册表
        indicator_ids = REGISTRY.get(industry, [])

        # 5. 展开定义
        defs = [INDICATOR_DEFS_MAP[iid] for iid in indicator_ids if iid in INDICATOR_DEFS_MAP]

        return SelectorResult(
            stock_code=code,
            industry=industry,
            chain_position=position,
            indicator_ids=indicator_ids,
            indicator_defs=defs,
        )

    def _get_industry_raw(self, code: str) -> str | None:
        """从 DataSource 获取原始行业名"""
        try:
            return self._source.get_stock_industry(code)
        except Exception:
            logger.exception("获取行业失败: code=%s", code)
            return None


__all__ = ["DynamicIndicatorSelector", "SelectorResult"]
