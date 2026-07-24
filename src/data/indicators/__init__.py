"""PD 动态指标体系 —— IndicatorRegistry + 产业链位置

基于实锤 API 验证的东方财富 496 个行业分类数据构建。
- `stock_individual_info_em()` 返回二级行业（如"银行Ⅱ"）
- 归一化到一级行业（31 个，与申万一级对齐）
- 每个行业映射 5-10 个关键 FinancialMetrics 指标
"""

from src.data.indicators.registry import (
    INDICATOR_DEFS,
    INDICATOR_DEFS_MAP,
    INDUSTRY_CHAIN_MAP,
    REGISTRY,
    IndicatorDef,
    IndustryChainPosition,
    normalize_industry,
)
from src.data.indicators.selector import DynamicIndicatorSelector, SelectorResult

__all__ = [
    "DynamicIndicatorSelector",
    "INDICATOR_DEFS",
    "INDICATOR_DEFS_MAP",
    "INDUSTRY_CHAIN_MAP",
    "IndicatorDef",
    "IndustryChainPosition",
    "REGISTRY",
    "SelectorResult",
    "normalize_industry",
]
