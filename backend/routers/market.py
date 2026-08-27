"""市场数据路由 —— /api/market/*

提供指数行情、板块排行、板块详情、AI 宏观简报等接口。

TD-020: 板块数据增强层 —— heat/chain_map/ai_analysis 接入真实数据源。
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Literal

import akshare as ak
import pandas as pd
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.async_utils import run_sync
from src.data.collector import DataCollector
from src.data.index_quote_runtime import (
    IndexLimitation,
    IndexSourceDiagnostic,
    get_index_quote_service,
)
from src.data.providers.base import safe_float, safe_str

logger = logging.getLogger("backend.market")
router = APIRouter(prefix="/api/market")
collector = DataCollector()
index_quote_service = get_index_quote_service()

# ── 响应模型（匹配 frontend/lib/types/market.ts） ──────────────

MarketDataStatus = Literal["success", "partial", "empty", "stale", "failed"]


class MarketLimitation(BaseModel):
    """可用响应仍存在的事实限制。"""

    code: str
    message: str
    index_code: str | None = None


class MarketSourceDiagnostic(BaseModel):
    index_code: str
    source_id: str
    upstream_id: str
    status: Literal[
        "success_data", "success_empty", "failed", "unsupported", "stale", "conflicted"
    ]
    latency_ms: int = Field(ge=0)
    as_of: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


class MarketMeta(BaseModel):
    """首页市场接口统一状态元数据。"""

    status: MarketDataStatus
    cached: bool = False
    latency_ms: int = 0
    missing_codes: list[str] = Field(default_factory=list)
    failed_sources: list[str] = Field(default_factory=list)
    limitations: list[MarketLimitation] = Field(default_factory=list)
    source_diagnostics: list[MarketSourceDiagnostic] = Field(default_factory=list)
    sort_requested: str | None = None
    sort_applied: str | None = None


class MarketErrorBody(BaseModel):
    code: str
    message: str


class MarketErrorResponse(BaseModel):
    error: MarketErrorBody
    meta: MarketMeta


class IndexQuoteResp(BaseModel):
    """三大指数行情（匹配 MarketIndex 类型）"""
    code: str
    name: str
    price: float = Field(gt=0.0)
    change: float = 0.0
    change_pct: float = 0.0
    as_of: datetime
    source_count: int = Field(ge=1)
    cached: bool = False


class SectorItemResp(BaseModel):
    """板块排行条目（匹配 SectorItem 类型）"""
    id: str
    name: str
    change_pct: float = 0.0
    fund_flow: float | None = None
    heat: str = "medium"
    top_stocks: list[str] = Field(default_factory=list)
    rank: int = 0


class SectorStockResp(BaseModel):
    """板块内个股（匹配 SectorStock 类型）"""
    code: str
    name: str
    price: float = 0.0
    change_pct: float = 0.0
    fund_flow: float | None = None
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
    fund_flow: float | None = None
    heat: str = "medium"
    chain_map: list[ChainStageResp] = Field(default_factory=list)
    ai_analysis: str = ""
    stocks: list[SectorStockResp] = Field(default_factory=list)


class MacroBriefResp(BaseModel):
    """AI 宏观简报（匹配 MacroBrief 类型）"""
    summary: str = Field(min_length=1)
    generated_at: str = ""
    market_style: str = ""
    risk_tips: list[str] = Field(default_factory=list)
    hot_topics: list[str] = Field(default_factory=list)


class IndicesEnvelope(BaseModel):
    data: list[IndexQuoteResp]
    meta: MarketMeta


class SectorsEnvelope(BaseModel):
    data: list[SectorItemResp]
    meta: MarketMeta


class SectorDetailEnvelope(BaseModel):
    data: SectorDetailResp
    meta: MarketMeta


class MacroBriefEnvelope(BaseModel):
    data: MacroBriefResp | None
    meta: MarketMeta


# ── 板块增强辅助函数 ──────────────────────────────────────────

_PD_FLOAT = float | None  # noqa: F841 — 类型别名


def _market_meta(
    status: MarketDataStatus,
    started_at: float,
    *,
    cached: bool = False,
    missing_codes: list[str] | None = None,
    failed_sources: list[str] | None = None,
    limitations: list[MarketLimitation] | None = None,
    source_diagnostics: list[MarketSourceDiagnostic] | None = None,
    sort_requested: str | None = None,
    sort_applied: str | None = None,
) -> dict[str, object]:
    return MarketMeta(
        status=status,
        cached=cached,
        latency_ms=round((time.time() - started_at) * 1000),
        missing_codes=missing_codes or [],
        failed_sources=failed_sources or [],
        limitations=limitations or [],
        source_diagnostics=source_diagnostics or [],
        sort_requested=sort_requested,
        sort_applied=sort_applied,
    ).model_dump()


def _market_failed(
    code: str,
    message: str,
    started_at: float,
    *,
    missing_codes: list[str] | None = None,
    failed_sources: list[str] | None = None,
    limitations: list[MarketLimitation] | None = None,
    source_diagnostics: list[MarketSourceDiagnostic] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content=MarketErrorResponse(
            error=MarketErrorBody(code=code, message=message),
            meta=MarketMeta(
                status="failed",
                latency_ms=round((time.time() - started_at) * 1000),
                missing_codes=missing_codes or [],
                failed_sources=failed_sources or [],
                limitations=limitations or [],
                source_diagnostics=source_diagnostics or [],
            ),
        ).model_dump(mode="json"),
    )


def _market_limitations(items: list[IndexLimitation]) -> list[MarketLimitation]:
    return [MarketLimitation.model_validate(item.model_dump()) for item in items]


def _market_source_diagnostics(
    items: list[IndexSourceDiagnostic],
) -> list[MarketSourceDiagnostic]:
    return [MarketSourceDiagnostic.model_validate(item.model_dump()) for item in items]


def _fetch_board_perf_df(board_type: str) -> pd.DataFrame:
    """获取板块行情 DataFrame（涨跌幅 + 主力净流入）

    列样例：
      板块代码, 板块名称, 涨跌幅, 主力净流入-净额, ...

    Args:
        board_type: "industry" 或 "concept"

    Returns:
        上游原始 DataFrame；异常由路由转换为稳定失败契约
    """
    if board_type == "industry":
        return ak.stock_board_industry_name_em()
    return ak.stock_board_concept_name_em()


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
    """仅从可核验关系证据构建产业链映射。

    当前板块成分股数据只包含代码、名称、价格和涨跌幅等行情字段，不能证明供应链或
    产业链的上下游关系。在真实关系数据源和对应契约获批前，安全返回空列表；不得用
    涨幅、价格、市值或排名推断产业链位置。

    Args:
        stocks_df: 板块成分股 DataFrame（当前不含关系证据）
        board_type: "industry" / "concept"

    Returns:
        空列表，表示当前没有可核验的产业链关系数据
    """
    _ = stocks_df, board_type
    return []


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


# ── 路由 ──────────────────────────────────────────────────────


@router.get(
    "/indices",
    response_model=IndicesEnvelope,
    responses={503: {"model": MarketErrorResponse}},
)
async def get_indices():
    """三大指数实时行情"""
    t0 = time.time()
    try:
        result = await run_sync(index_quote_service.collect)
    except Exception:
        logger.exception("多源指数汇总发生未处理异常")
        return _market_failed(
            "MARKET_INDICES_FAILED", "指数行情暂时不可用", t0,
            failed_sources=["eastmoney", "sina"],
        )
    limitations = _market_limitations(result.limitations)
    diagnostics = _market_source_diagnostics(result.source_diagnostics)
    if result.status == "failed":
        return _market_failed(
            result.error_code or "MARKET_INDICES_FAILED",
            "指数双源校验失败",
            t0,
            missing_codes=result.missing_codes,
            failed_sources=result.failed_sources,
            limitations=limitations,
            source_diagnostics=diagnostics,
        )
    return {
        "data": [item.model_dump() for item in result.quotes],
        "meta": _market_meta(
            result.status,
            t0,
            cached=any(item.cached for item in result.quotes),
            missing_codes=result.missing_codes,
            failed_sources=result.failed_sources,
            limitations=limitations,
            source_diagnostics=diagnostics,
        ),
    }


@router.get(
    "/sectors",
    response_model=SectorsEnvelope,
    responses={503: {"model": MarketErrorResponse}},
)
async def get_sectors(sort: str = Query("fund_flow", description="排序维度")):
    """板块排行（行业 + 概念），含真实涨跌幅和资金流向"""
    t0 = time.time()
    items: list[SectorItemResp] = []
    failed_sources: list[str] = []
    fund_flow_missing_sources: list[str] = []

    # 行业板块 — 直接调 akshare 获取完整 DataFrame
    try:
        df_ind = await run_sync(_fetch_board_perf_df, "industry")
    except Exception:
        logger.exception("获取行业板块行情失败")
        failed_sources.append("industry")
        df_ind = pd.DataFrame()
    if not df_ind.empty:
        industry_has_fund_flow = "主力净流入-净额" in df_ind.columns
        if not industry_has_fund_flow:
            fund_flow_missing_sources.append("industry")
        for i, (_, row) in enumerate(df_ind.iterrows()):
            code = safe_str(row.get("板块代码", ""))
            name = safe_str(row.get("板块名称", ""))
            items.append(SectorItemResp(
                id=code, name=name, rank=i + 1,
                change_pct=safe_float(row.get("涨跌幅", 0.0)),
                fund_flow=(
                    safe_float(row.get("主力净流入-净额"))
                    if industry_has_fund_flow else None
                ),
            ))

    # 概念板块
    try:
        df_con = await run_sync(_fetch_board_perf_df, "concept")
    except Exception:
        logger.exception("获取概念板块行情失败")
        failed_sources.append("concept")
        df_con = pd.DataFrame()
    if not df_con.empty:
        concept_has_fund_flow = "主力净流入-净额" in df_con.columns
        if not concept_has_fund_flow:
            fund_flow_missing_sources.append("concept")
        offset = len(items)
        for i, (_, row) in enumerate(df_con.iterrows()):
            code = safe_str(row.get("板块代码", ""))
            name = safe_str(row.get("板块名称", ""))
            items.append(SectorItemResp(
                id=code, name=name, rank=offset + i + 1,
                change_pct=safe_float(row.get("涨跌幅", 0.0)),
                fund_flow=(
                    safe_float(row.get("主力净流入-净额"))
                    if concept_has_fund_flow else None
                ),
            ))

    if not items and failed_sources:
        return _market_failed(
            "MARKET_SECTORS_FAILED", "板块行情暂时不可用", t0,
            failed_sources=failed_sources,
        )
    limitations: list[MarketLimitation] = []
    if fund_flow_missing_sources:
        limitations.append(MarketLimitation(
            code="FUND_FLOW_UNAVAILABLE",
            message=(
                "当前板块排行来源未提供主力资金流字段，fund_flow 返回 null，"
                "不得按资金流解释或排序"
            ),
        ))

    sort_applied = "upstream_order"
    if sort == "fund_flow" and items and all(item.fund_flow is not None for item in items):
        items.sort(key=lambda item: item.fund_flow or 0.0, reverse=True)
        sort_applied = "fund_flow"
    elif sort == "change_pct" and items:
        items.sort(key=lambda item: item.change_pct, reverse=True)
        sort_applied = "change_pct"
    for rank, item in enumerate(items, start=1):
        item.rank = rank

    status: MarketDataStatus = "empty" if not items else (
        "partial" if failed_sources or limitations else "success"
    )
    return {
        "data": [i.model_dump() for i in items],
        "meta": _market_meta(
            status,
            t0,
            failed_sources=failed_sources,
            limitations=limitations,
            sort_requested=sort,
            sort_applied=sort_applied,
        ),
    }


@router.get("/sector/{sector_id:str}", response_model=SectorDetailEnvelope)
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
    fund_flow: float | None = None
    if not board_perf_df.empty:
        matched = board_perf_df[board_perf_df["板块代码"].astype(str) == sector_id]
        if not matched.empty:
            row = matched.iloc[0]
            change_pct = safe_float(row.get("涨跌幅", 0.0))
            if "主力净流入-净额" in board_perf_df.columns:
                fund_flow = safe_float(row.get("主力净流入-净额"))

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
    limitations = [MarketLimitation(
        code="FUND_FLOW_UNAVAILABLE",
        message="板块或成分股缺少已核验资金流字段，未知值返回 null",
    )]
    return {
        "data": detail.model_dump(),
        "meta": _market_meta("partial", t0, limitations=limitations),
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


@router.get(
    "/brief",
    response_model=MacroBriefEnvelope,
    responses={503: {"model": MarketErrorResponse}},
)
async def get_macro_brief():
    """AI 宏观简报"""
    t0 = time.time()
    try:
        result = await run_sync(index_quote_service.collect)
    except Exception:
        logger.exception("宏观简报多源指数汇总发生未处理异常")
        return _market_failed(
            "MARKET_BRIEF_FAILED", "宏观简报输入暂时不可用", t0,
            failed_sources=["eastmoney", "sina"],
        )
    limitations = _market_limitations(result.limitations)
    diagnostics = _market_source_diagnostics(result.source_diagnostics)
    if result.status == "failed":
        return _market_failed(
            "MARKET_BRIEF_FAILED",
            "宏观简报指数输入未通过双源校验",
            t0,
            missing_codes=result.missing_codes,
            failed_sources=result.failed_sources,
            limitations=limitations,
            source_diagnostics=diagnostics,
        )
    if not result.quotes:
        return {
            "data": None,
            "meta": _market_meta(
                result.status,
                t0,
                missing_codes=result.missing_codes,
                failed_sources=result.failed_sources,
                limitations=limitations,
                source_diagnostics=diagnostics,
            ),
        }
    lines: list[str] = []
    for i in result.quotes:
        lines.append(f"  {i.name}: {i.price:.2f}（{i.change_pct:+.2f}%）")

    summary = " | ".join(lines)
    brief = MacroBriefResp(
        summary=summary,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    return {
        "data": brief.model_dump(),
        "meta": _market_meta(
            result.status,
            t0,
            cached=any(item.cached for item in result.quotes),
            missing_codes=result.missing_codes,
            failed_sources=result.failed_sources,
            limitations=limitations,
            source_diagnostics=diagnostics,
        ),
    }


class HotNewsItemResp(BaseModel):
    """热点快讯条目"""
    title: str = Field(min_length=1)
    date: str | None = None
    source: str = Field(min_length=1)
    url: str = ""


class HotNewsEnvelope(BaseModel):
    data: list[HotNewsItemResp]
    meta: MarketMeta


_HOT_NEWS_CACHE: dict[str, object] = {}
_HOT_NEWS_TTL = 120  # 2 分钟
_MARKET_DATA_STATUSES: tuple[MarketDataStatus, ...] = (
    "success",
    "partial",
    "empty",
    "stale",
    "failed",
)


def _first_text(row: pd.Series, fields: tuple[str, ...]) -> str:
    for field in fields:
        value = safe_str(row.get(field, ""))
        if value:
            return value
    return ""


def _cached_hot_news_status(value: object) -> MarketDataStatus:
    return value if value in _MARKET_DATA_STATUSES else "success"


def _cached_hot_news_limitations(value: object) -> list[MarketLimitation]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, MarketLimitation)]


@router.get(
    "/hot-news",
    response_model=HotNewsEnvelope,
    responses={503: {"model": MarketErrorResponse}},
)
async def get_hot_news():
    """热点快讯 —— 全市场新闻聚合"""
    t0 = time.time()
    now = datetime.now().timestamp()

    # 检查缓存
    cached = _HOT_NEWS_CACHE.get("data")
    cached_at = _HOT_NEWS_CACHE.get("ts", 0.0)
    if (
        isinstance(cached, list)
        and isinstance(cached_at, (int, float))
        and (now - cached_at) < _HOT_NEWS_TTL
    ):
        return {
            "data": cached,
            "meta": _market_meta(
                _cached_hot_news_status(_HOT_NEWS_CACHE.get("status")),
                t0,
                cached=True,
                limitations=_cached_hot_news_limitations(
                    _HOT_NEWS_CACHE.get("limitations"),
                ),
            ),
        }

    try:
        df: pd.DataFrame = await run_sync(ak.stock_news_main_cx)
        if df.empty:
            return {"data": [], "meta": _market_meta("empty", t0)}
        title_fields = ("title", "summary", "标题", "新闻标题")
        if not any(field in df.columns for field in title_fields):
            logger.error("热点新闻字段损坏: columns=%s", list(df.columns))
            return _market_failed(
                "HOT_NEWS_SCHEMA_INVALID", "热点新闻字段暂时不兼容", t0,
                failed_sources=["caixin"],
            )
        items: list[dict[str, object]] = []
        missing_published_at = False
        skipped_items = 0
        for _, row in df.head(30).iterrows():
            title = _first_text(row, title_fields)
            url = _first_text(row, ("url", "链接", "新闻链接"))
            if not title:
                skipped_items += 1
                continue
            published_at = _first_text(
                row, ("date", "time", "datetime", "发布时间", "发布日期"),
            ) or None
            if published_at is None:
                missing_published_at = True
            items.append(HotNewsItemResp(
                title=title,
                date=published_at,
                source=_first_text(row, ("source", "来源")) or "财新数据通",
                url=url,
            ).model_dump())
        if not items:
            return _market_failed(
                "HOT_NEWS_SCHEMA_INVALID", "热点新闻没有可用标题", t0,
                failed_sources=["caixin"],
            )
        limitations: list[MarketLimitation] = []
        if missing_published_at:
            limitations.append(MarketLimitation(
                code="PUBLISHED_AT_MISSING",
                message="当前来源未提供发布时间，未使用抓取时间冒充发布时间",
            ))
        if skipped_items:
            limitations.append(MarketLimitation(
                code="INVALID_ITEMS_SKIPPED",
                message=f"{skipped_items} 条记录缺少标题，已跳过",
            ))
        status: MarketDataStatus = "partial" if limitations else "success"
        _HOT_NEWS_CACHE["data"] = items
        _HOT_NEWS_CACHE["ts"] = now
        _HOT_NEWS_CACHE["status"] = status
        _HOT_NEWS_CACHE["limitations"] = limitations
        return {
            "data": items,
            "meta": _market_meta(status, t0, limitations=limitations),
        }
    except Exception as e:
        logger.exception("热点快讯获取失败: %s", e)
        # 有缓存则返回过期缓存
        if isinstance(cached, list) and cached:
            return {
                "data": cached,
                "meta": _market_meta(
                    "stale",
                    t0,
                    cached=True,
                    limitations=[MarketLimitation(
                        code="UPSTREAM_FAILED",
                        message="当前来源失败，返回过期缓存",
                    )],
                ),
            }
        return _market_failed(
            "HOT_NEWS_FAILED", "热点新闻暂时不可用", t0,
            failed_sources=["caixin"],
        )
