"""数据层 Pydantic 模型 —— 数据契约（ADR-001/008）

所有跨模块数据传输使用此模块定义的 BaseModel。
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class StockInfo(BaseModel):
    """A 股股票基本信息"""
    code: str
    name: str
    market: str = ""


class StockQuote(BaseModel):
    """实时行情快照"""
    code: str
    name: str
    price: float = Field(ge=0.0)
    change: float
    change_pct: float
    volume: int = Field(ge=0)
    amount: float = Field(default=0.0, ge=0.0)
    high: float = Field(default=0.0, ge=0.0)
    low: float = Field(default=0.0, ge=0.0)
    open_: float = Field(default=0.0, ge=0.0)
    prev_close: float = Field(default=0.0, ge=0.0)
    market_cap: float = Field(default=0.0, ge=0.0, description="总市值(元)")


class KLine(BaseModel):
    """K 线数据点"""
    date: str
    open: float = Field(ge=0.0)
    close: float = Field(ge=0.0)
    high: float = Field(ge=0.0)
    low: float = Field(ge=0.0)
    volume: int = Field(ge=0)
    amount: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def validate_kline_ranges(self) -> "KLine":
        """验证 K 线 OHLC 合理性"""
        if self.high < self.low:
            raise ValueError(f"high ({self.high}) must be >= low ({self.low})")
        if self.open < self.low or self.open > self.high:
            raise ValueError(
                f"open ({self.open}) must be within [{self.low}, {self.high}]"
            )
        if self.close < self.low or self.close > self.high:
            raise ValueError(
                f"close ({self.close}) must be within [{self.low}, {self.high}]"
            )
        return self


class NewsItem(BaseModel):
    """个股新闻"""
    code: str
    title: str
    date: str
    content: str = ""
    source: str = ""
    url: str = ""


class CapitalFlowItem(BaseModel):
    """个股资金流向数据点（主力/散户/机构净流入）"""

    date: str = ""
    main_net_inflow: float = Field(default=0.0, description="主力净流入（大单+超大单）")
    retail_net_inflow: float = Field(default=0.0, description="小单净流入（散户）")
    institutional_net_inflow: float = Field(default=0.0, description="大单净流入（机构）")


BoardType = Literal["industry", "concept"]


class BoardInfo(BaseModel):
    """板块信息"""
    code: str
    name: str
    board_type: BoardType


class BriefSection(BaseModel):
    """简报的一个区块

    表示市场简报中的一个分区，如行情层、新闻层、情绪层、基本面层。
    """

    title: str  # 如 "行情层", "新闻层"
    content: str  # 格式化文本
    has_data: bool = False


class MarketBrief(BaseModel):
    """结构化市场简报

    按 4 个维度（行情/新闻/情绪/基本面）分区的市场简报。
    C1 实现：情绪层和基本面层为占位区段，待后续接入实际数据源。
    """

    stock_code: str = ""
    stock_name: str = ""
    sections: dict[str, BriefSection] = Field(default_factory=dict)

    def to_text(self) -> str:
        """转纯文本供 LLM 消费"""
        if self.stock_name:
            lines = [f"📊 市场简报 — {self.stock_name} ({self.stock_code})"]
        elif self.stock_code:
            lines = [f"📊 市场简报 — {self.stock_code}"]
        else:
            lines = ["📊 市场简报"]

        lines.append("━" * 35)
        lines.append("")

        for key, section in self.sections.items():
            lines.append(f"----- {section.title} -----")
            lines.append(section.content if section.has_data else f"（{section.content}）")
            lines.append("")

        return "\n".join(lines).rstrip()


class FinancialMetrics(BaseModel):
    """个股核心财务指标（季度）

    从 akshare stock_financial_analysis_indicator 提取的关键指标，
    用于基本面价值分析。报告期为季度末日期（如 "2024-12-31"）。

    不含 PE/PB（需要股价数据在消费层组合计算）。

    Attributes:
        stock_code: 股票代码
        report_date: 报告期
        eps: 摊薄每股收益(元)
        book_value_per_share: 每股净资产_调整后(元)
        operating_cf_per_share: 每股经营性现金流(元)
        roe: 净资产收益率(%)
        roa: 总资产利润率(%)
        gross_margin: 销售毛利率(%)
        net_profit_margin: 销售净利率(%)
        revenue_growth: 主营业务收入增长率(%)
        net_profit_growth: 净利润增长率(%)
        debt_ratio: 资产负债率(%)
        current_ratio: 流动比率
        quick_ratio: 速动比率
        inventory_turnover: 存货周转率(次)
        asset_turnover: 总资产周转率(次)
        total_assets: 总资产(元)
        operating_revenue: 主营业务利润(元)
    """

    stock_code: str
    report_date: str = ""

    # ── 每股指标 ──
    eps: float = Field(default=0.0, description="摊薄每股收益(元)")
    book_value_per_share: float = Field(default=0.0, ge=0.0, description="每股净资产_调整后(元)")
    operating_cf_per_share: float = Field(default=0.0, description="每股经营性现金流(元)")

    # ── 盈利能力 ──
    roe: float = Field(default=0.0, description="净资产收益率(%)")
    roa: float = Field(default=0.0, description="总资产利润率(%)")
    gross_margin: float = Field(default=0.0, description="销售毛利率(%)")
    net_profit_margin: float = Field(default=0.0, description="销售净利率(%)")

    # ── 增长能力 ──
    revenue_growth: float = Field(default=0.0, description="主营业务收入增长率(%)")
    net_profit_growth: float = Field(default=0.0, description="净利润增长率(%)")

    # ── 财务健康 ──
    debt_ratio: float = Field(default=0.0, ge=0.0, le=100.0, description="资产负债率(%)")
    current_ratio: float = Field(default=0.0, ge=0.0, description="流动比率")
    quick_ratio: float = Field(default=0.0, ge=0.0, description="速动比率")

    # ── 运营效率 ──
    inventory_turnover: float = Field(default=0.0, ge=0.0, description="存货周转率(次)")
    asset_turnover: float = Field(default=0.0, ge=0.0, description="总资产周转率(次)")

    # ── 规模 ──
    total_assets: float = Field(default=0.0, ge=0.0, description="总资产(元)")
    operating_revenue: float = Field(default=0.0, description="主营业务利润(元)")


class ValuationMetrics(BaseModel):
    """个股估值比率（由财务指标 + 股价计算）

    基于最新财报指标和当前股价计算关键估值比率。
    PE = 股价 / EPS（市盈率）
    PB = 股价 / 每股净资产（市净率）
    PS = 总市值 / 主营业务收入（市销率）

    所有字段 ge=0.0：负估值（亏损公司）标记为 0.0 而非负值。
    连续亏损公司 PE = 0.0（负 PE 无经济含义）。
    """

    stock_code: str
    report_date: str = Field(default="", description="财务数据报告期")
    pe: float = Field(default=0.0, ge=0.0, description="市盈率 = 股价 / EPS")
    pb: float = Field(default=0.0, ge=0.0, description="市净率 = 股价 / 每股净资产")
    ps: float = Field(default=0.0, ge=0.0, description="市销率 = 总市值 / 主营业务收入")
    market_cap: float = Field(default=0.0, ge=0.0, description="总市值(元)")


__all__ = [
    "BoardInfo",
    "BoardType",
    "BriefSection",
    "CapitalFlowItem",
    "FinancialMetrics",
    "KLine",
    "MarketBrief",
    "NewsItem",
    "StockInfo",
    "StockQuote",
    "ValuationMetrics",
]
