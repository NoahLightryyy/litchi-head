"""数据层 Pydantic 模型 —— 数据契约（ADR-001/008）

所有跨模块数据传输使用此模块定义的 BaseModel。
"""

from typing import Literal

from pydantic import BaseModel, Field


class StockInfo(BaseModel):
    """A 股股票基本信息"""
    code: str
    name: str
    market: str = ""


class StockQuote(BaseModel):
    """实时行情快照"""
    code: str
    name: str
    price: float
    change: float
    change_pct: float
    volume: int
    amount: float = 0.0
    high: float = 0.0
    low: float = 0.0
    open_: float = 0.0
    prev_close: float = 0.0


class KLine(BaseModel):
    """K 线数据点"""
    date: str
    open: float
    close: float
    high: float
    low: float
    volume: int
    amount: float = 0.0


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


__all__ = [
    "BoardInfo",
    "BoardType",
    "BriefSection",
    "CapitalFlowItem",
    "KLine",
    "MarketBrief",
    "NewsItem",
    "StockInfo",
    "StockQuote",
]
