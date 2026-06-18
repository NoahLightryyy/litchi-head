"""市场数据路由 —— /api/market/*

提供指数行情、板块排行、板块详情、AI 宏观简报等接口。

TD-020: 板块数据增强层 —— heat/chain_map/ai_analysis 接入真实数据源。
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

import akshare as ak
import pandas as pd
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.async_utils import run_sync
from src.data.collector import DataCollector
from src.data.models import StockQuote as BackendQuote
from src.data.providers.base import safe_float, safe_str

logger = logging.getLogger("backend.market")
router = APIRouter(prefix="/api/market")
collector = DataCollector()

# ── 响应模型（匹配 frontend/lib/types/market.ts） ──────────────


class IndexQuoteResp(BaseModel):
    """三大指数行情（匹配 MarketIndex 类型）"""
    code: str
    name: str
    price: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0


class SectorItemResp(BaseModel):
    """板块排行条目（匹配 SectorItem 类型）"""
    id: str
    name: str
    change_pct: float = 0.0
    fund_flow: float = 0.0
    heat: str = "medium"
    top_stocks: list[str] = Field(default_factory=list)
    rank: int = 0


class SectorStockResp(BaseModel):
    """板块内个股（匹配 SectorStock 类型）"""
    code: str
    name: str
    price: float = 0.0
    change_pct: float = 0.0
    fund_flow: float = 0.0
    ai_rating: str = "B"


class ChainNodeResp(BaseModel):
    """产业链节点（匹配 ChainNode 类型）"""
    name: str
    companies: list[str] = Field(default_factory=list)
    is_bottleneck: bool = False


class ChainStageResp(BaseModel):
    """产业链阶段（匹配 ChainStage 类型）"""
    stage: str
    description: str = ""
    nodes: list[ChainNodeResp] = Field(default_factory=list)


class SectorDetailResp(BaseModel):
    """板块详情（匹配 SectorDetail 类型）"""
    id: str
    name: str
    change_pct: float = 0.0
    fund_flow: float = 0.0
    heat: str = "medium"
    chain_map: list[ChainStageResp] = Field(default_factory=list)
    ai_analysis: str = ""
    stocks: list[SectorStockResp] = Field(default_factory=list)


class MacroBriefResp(BaseModel):
    """AI 宏观简报（匹配 MacroBrief 类型）"""
    summary: str = "暂无数据"
    generated_at: str = ""
    market_style: str = ""
    risk_tips: list[str] = Field(default_factory=list)
    hot_topics: list[str] = Field(default_factory=list)


# ── 板块增强辅助函数 ──────────────────────────────────────────

_PD_FLOAT = float | None  # noqa: F841 — 类型别名


def _fetch_board_perf_df(board_type: str) -> pd.DataFrame:
    """获取板块行情 DataFrame（涨跌幅 + 主力净流入）

    列样例：
      板块代码, 板块名称, 涨跌幅, 主力净流入-净额, ...

    Args:
        board_type: "industry" 或 "concept"

    Returns:
        DataFrame（失败时返回空 DataFrame）
    """
    try:
        if board_type == "industry":
            return ak.stock_board_industry_name_em()
        return ak.stock_board_concept_name_em()
    except Exception:
        logger.exception("获取板块行情失败: board_type=%s", board_type)
        return pd.DataFrame()


def _fetch_board_stocks_df(sector_id: str, board_type: str) -> pd.DataFrame:
    """获取板块成分股行情

    Args:
        sector_id: BK 代码
        board_type: "industry" 或 "concept"

    Returns:
        DataFrame（列：代码, 名称, 现价, 涨跌幅, 主力净流入）
    """
    try:
        if board_type == "industry":
            return ak.stock_board_industry_cons_em(symbol=sector_id)
        return ak.stock_board_concept_cons_em(symbol=sector_id)
    except Exception:
        logger.exception("获取板块成分股失败: sector_id=%s", sector_id)
        return pd.DataFrame()


def _calc_heat(
    stocks_df: pd.DataFrame,
    change_col: str = "涨跌幅",
) -> str:
    """从成分股涨跌数据计算板块热度

    规则：
      - up_ratio >= 60% → "high"
      - 40% <= up_ratio < 60% → "medium"
      - up_ratio < 40% → "low"
      成分股不足 3 只 → "medium"

    Returns:
        "high" / "medium" / "low"
    """
    if stocks_df.empty or len(stocks_df) < 3:
        return "medium"
    count = len(stocks_df)
    up = sum(
        1 for _, r in stocks_df.iterrows()
        if safe_float(r.get(change_col, 0.0)) > 0
    )
    up_ratio = up / count * 100
    if up_ratio >= 60:
        return "high"
    if up_ratio >= 40:
        return "medium"
    return "low"


def _build_top_stocks(
    stocks_df: pd.DataFrame,
    sort_col: str = "涨跌幅",
    limit: int = 5,
) -> list[str]:
    """取板块内涨幅前 N 的股票名称"""
    if stocks_df.empty:
        return []
    col = sort_col if sort_col in stocks_df.columns else "涨跌幅"
    df_sorted = stocks_df.sort_values(col, ascending=False)
    names: list[str] = []
    for _, r in df_sorted.head(limit).iterrows():
        names.append(safe_str(r.get("名称", "")))
    return names


def _build_chain_map(
    stocks_df: pd.DataFrame,
    board_type: str,
) -> list[ChainStageResp]:
    """从成分股数据构建简易产业链映射

    按价格 + 涨幅分层：龙头层（排名前 20%）、中坚层（中间 60%）、基础层（后 20%）。

    Args:
        stocks_df: 板块成分股 DataFrame
        board_type: "industry" / "concept"

    Returns:
        产业链阶段列表
    """
    if stocks_df.empty or len(stocks_df) < 6:
        return []

    # 按涨幅排序
    sorted_df = stocks_df.sort_values("涨跌幅", ascending=False)
    n = len(sorted_df)
    top_n = max(n // 5, 2)
    base_n = max(n // 5, 2)
    mid_n = n - top_n - base_n

    top_names = [safe_str(r["名称"]) for _, r in sorted_df.head(top_n).iterrows()]
    base_names = [safe_str(r["名称"]) for _, r in sorted_df.tail(base_n).iterrows()]
    mid_names = [
        safe_str(r["名称"]) for _, r in sorted_df.iloc[top_n:top_n + mid_n].iterrows()
    ]

    stages: list[ChainStageResp] = [
        ChainStageResp(
            stage="领涨龙头",
            description=f"涨幅前 {top_n} 只成分股",
            nodes=[
                ChainNodeResp(name="龙头股", companies=top_names[:5], is_bottleneck=False),
            ],
        ),
        ChainStageResp(
            stage="中坚力量",
            description="涨幅居中的成分股",
            nodes=[
                ChainNodeResp(name="中坚股", companies=mid_names[:8], is_bottleneck=False),
            ],
        ),
        ChainStageResp(
            stage="基础层",
            description=f"涨幅后 {base_n} 只成分股",
            nodes=[
                ChainNodeResp(name="基础股", companies=base_names[:5], is_bottleneck=True),
            ],
        ),
    ]
    return stages


def _build_ai_analysis(
    board_name: str,
    stocks_df: pd.DataFrame,
    heat: str,
    board_type: str,
) -> str:
    """从板块数据生成 AI 分析文本"""
    if stocks_df.empty:
        return f"【{board_name}】暂无足够数据生成分析。"

    n = len(stocks_df)
    up = sum(
        1 for _, r in stocks_df.iterrows()
        if safe_float(r.get("涨跌幅", 0.0)) > 0
    )
    down = n - up
    avg_change = (
        sum(safe_float(r.get("涨跌幅", 0.0)) for _, r in stocks_df.iterrows()) / n
    )

    # 板块特征标签
    heat_label = {"high": "活跃", "medium": "温和", "low": "低迷"}.get(heat, "温和")

    lines = [
        f"📊 **{board_name}**（{'行业' if board_type == 'industry' else '概念'}板块）",
        "",
        f"- 成分股共 {n} 只，上涨 {up} 只，下跌 {down} 只",
        f"- 平均涨跌幅 {avg_change:+.2f}%",
        f"- 市场热度：{heat_label}",
        "",
    ]

    if up > down * 1.5:
        lines.append("板块整体表现强势，多头占优。")
    elif down > up * 1.5:
        lines.append("板块整体表现疲弱，空头占优。")
    else:
        lines.append("板块多空相对均衡，震荡为主。")

    lines.append("")
    lines.append("*数据来源：东方财富 / akshare*")
    return "\n".join(lines)


def _detect_board_type(sector_id: str) -> str:
    """判断板块类型（行业 / 概念）"""
    industry = collector.get_industry_boards()
    if any(b.code == sector_id for b in industry):
        return "industry"
    return "concept"


# ── 辅助函数 ──────────────────────────────────────────────────

_INDEX_CODES: list[tuple[str, str]] = [
    ("000001", "上证指数"),
    ("399001", "深证成指"),
    ("399006", "创业板指"),
]


def _pick_index(quotes: list[BackendQuote], code: str, name: str) -> IndexQuoteResp:
    for q in quotes:
        if q.code == code:
            return IndexQuoteResp(
                code=q.code, name=name, price=q.price,
                change=q.change, change_pct=q.change_pct,
            )
    return IndexQuoteResp(code=code, name=name)


# ── 路由 ──────────────────────────────────────────────────────


@router.get("/indices")
async def get_indices():
    """三大指数实时行情"""
    t0 = time.time()
    quotes = await run_sync(collector.get_realtime_quotes)
    indices = [_pick_index(quotes, code, name) for code, name in _INDEX_CODES]
    return {
        "data": [i.model_dump() for i in indices],
        "meta": {"cached": False, "latency_ms": round((time.time() - t0) * 1000)},
    }


@router.get("/sectors")
async def get_sectors(sort: str = Query("fund_flow", description="排序维度")):
    """板块排行（行业 + 概念），含真实涨跌幅和资金流向"""
    t0 = time.time()
    items: list[SectorItemResp] = []

    # 行业板块 — 直接调 akshare 获取完整 DataFrame
    df_ind = await run_sync(_fetch_board_perf_df, "industry")
    if not df_ind.empty:
        for i, (_, row) in enumerate(df_ind.iterrows()):
            code = safe_str(row.get("板块代码", ""))
            name = safe_str(row.get("板块名称", ""))
            items.append(SectorItemResp(
                id=code, name=name, rank=i + 1,
                change_pct=safe_float(row.get("涨跌幅", 0.0)),
                fund_flow=safe_float(row.get("主力净流入-净额", 0.0)),
            ))

    # 概念板块
    df_con = await run_sync(_fetch_board_perf_df, "concept")
    if not df_con.empty:
        offset = len(items)
        for i, (_, row) in enumerate(df_con.iterrows()):
            code = safe_str(row.get("板块代码", ""))
            name = safe_str(row.get("板块名称", ""))
            items.append(SectorItemResp(
                id=code, name=name, rank=offset + i + 1,
                change_pct=safe_float(row.get("涨跌幅", 0.0)),
                fund_flow=safe_float(row.get("主力净流入-净额", 0.0)),
            ))

    return {
        "data": [i.model_dump() for i in items],
        "meta": {"cached": False, "latency_ms": round((time.time() - t0) * 1000)},
    }


@router.get("/sector/{sector_id:str}")
async def get_sector_detail(sector_id: str):
    """板块详情 — 含成分股 + 热度 + AI 分析 + 产业链映射"""
    t0 = time.time()

    # 判断板块类型并获取成分股
    board_type = await run_sync(_detect_board_type, sector_id)
    stocks_df = await run_sync(_fetch_board_stocks_df, sector_id, board_type)
    board_perf_df = await run_sync(_fetch_board_perf_df, board_type)

    # 板块基本信息
    board_name = sector_id
    if not board_perf_df.empty:
        matched = board_perf_df[board_perf_df["板块代码"].astype(str) == sector_id]
        if not matched.empty:
            row = matched.iloc[0]
            board_name = safe_str(row.get("板块名称", sector_id))

    # 热度
    heat = _calc_heat(stocks_df)

    # 板块涨跌幅 + 资金流
    change_pct = 0.0
    fund_flow = 0.0
    if not board_perf_df.empty:
        matched = board_perf_df[board_perf_df["板块代码"].astype(str) == sector_id]
        if not matched.empty:
            row = matched.iloc[0]
            change_pct = safe_float(row.get("涨跌幅", 0.0))
            fund_flow = safe_float(row.get("主力净流入-净额", 0.0))

    # 成分股列表
    stocks: list[SectorStockResp] = []
    if not stocks_df.empty:
        for _, row in stocks_df.iterrows():
            stocks.append(SectorStockResp(
                code=safe_str(row.get("代码", "")),
                name=safe_str(row.get("名称", "")),
                price=safe_float(row.get("现价", 0.0)),
                change_pct=safe_float(row.get("涨跌幅", 0.0)),
                ai_rating=_calc_rating(safe_float(row.get("涨跌幅", 0.0))),
            ))

    # AI 分析
    ai_analysis = _build_ai_analysis(board_name, stocks_df, heat, board_type)

    # 产业链映射
    chain_map = _build_chain_map(stocks_df, board_type)

    detail = SectorDetailResp(
        id=sector_id, name=board_name,
        change_pct=change_pct, fund_flow=fund_flow,
        heat=heat, stocks=stocks,
        ai_analysis=ai_analysis, chain_map=chain_map,
    )
    return {
        "data": detail.model_dump(),
        "meta": {"cached": False, "latency_ms": round((time.time() - t0) * 1000)},
    }


def _calc_rating(change_pct: float) -> str:
    """根据涨跌幅给个股评级"""
    if change_pct >= 5:
        return "A"
    if change_pct >= 2:
        return "B+"
    if change_pct >= 0:
        return "B"
    if change_pct >= -3:
        return "C"
    return "D"


@router.get("/brief")
async def get_macro_brief():
    """AI 宏观简报"""
    t0 = time.time()
    quotes = await run_sync(collector.get_realtime_quotes)
    indices = [_pick_index(quotes, code, name) for code, name in _INDEX_CODES]
    lines: list[str] = []
    for i in indices:
        if i.price > 0:
            lines.append(f"  {i.name}: {i.price:.2f}（{i.change_pct:+.2f}%）")

    summary = "暂无数据" if not lines else " | ".join(lines)
    brief = MacroBriefResp(
        summary=summary,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    return {
        "data": brief.model_dump(),
        "meta": {"cached": False, "latency_ms": round((time.time() - t0) * 1000)},
    }
