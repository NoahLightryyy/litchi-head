"""市场数据路由 —— /api/market/*

提供指数行情、板块排行、板块详情、AI 宏观简报等接口。

TD-020: 板块数据增强层 —— heat/chain_map/ai_analysis 接入真实数据源。
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import datetime
from typing import Literal

import pandas as pd
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.async_utils import DATA_TIMEOUT, BoundedSyncRunner, run_sync
from src.data.chain_evidence import ChainEvidenceMap, get_sector_chain
from src.data.collector import DataCollector
from src.data.index_quote_runtime import (
    IndexLimitation,
    IndexSourceDiagnostic,
    get_index_quote_service,
)
from src.data.providers.base import safe_float, safe_str
from src.data.providers.caixin_news import fetch_caixin_news
from src.data.providers.eastmoney_boards import (
    BoardKind,
    BoardMembersSnapshot,
    BoardSnapshot,
    board_snapshots,
)
from src.data.providers.sina_boards import sina_boards

logger = logging.getLogger("backend.market")
router = APIRouter(prefix="/api/market")
collector = DataCollector()
index_quote_service = get_index_quote_service()
_sector_source_runner = BoundedSyncRunner(
    max_workers=2,
    thread_name_prefix="market-sector-source",
)

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


class SectorDetailErrorBody(BaseModel):
    code: Literal[
        "MARKET_SECTOR_DETAIL_TIMEOUT",
        "MARKET_SECTOR_DETAIL_FAILED",
    ]
    message: str
    retryable: Literal[True] = True
    retry_mode: Literal["client_controlled"] = "client_controlled"


class SectorDetailErrorResponse(BaseModel):
    error: SectorDetailErrorBody
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
    display_source: str | None = None


class SectorItemResp(BaseModel):
    """板块排行条目（匹配 SectorItem 类型）"""
    id: str
    name: str
    change_pct: float = 0.0
    fund_flow: float | None = Field(default=None, description="主力净流入，单位亿元")
    heat: str = "medium"
    top_stocks: list[str] = Field(default_factory=list)
    rank: int = 0
    category: Literal["industry", "concept"]
    as_of: datetime | None = None
    source: Literal["eastmoney", "sina"] = "eastmoney"
    net_flow: float | None = Field(default=None, description="来源口径资金净流入，亿元；非主力")
    service_updated_at: datetime | None = None
    snapshot_may_be_delayed: bool = False


class SectorStockResp(BaseModel):
    """板块内个股（匹配 SectorStock 类型）"""
    code: str
    name: str
    price: float = 0.0
    change_pct: float = 0.0
    fund_flow: float | None = Field(default=None, description="主力净流入，单位亿元")
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
    change_pct: float | None = Field(default=None, description="板块涨跌幅，缺报价为null")
    fund_flow: float | None = Field(default=None, description="主力净流入，单位亿元")
    heat: str = "medium"
    chain_map: list[ChainStageResp] = Field(default_factory=list)
    chain_evidence: ChainEvidenceMap | None = None
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


def _sector_detail_failed(
    code: Literal[
        "MARKET_SECTOR_DETAIL_TIMEOUT",
        "MARKET_SECTOR_DETAIL_FAILED",
    ],
    message: str,
    started_at: float,
    *,
    failed_sources: list[str],
) -> JSONResponse:
    """Return the frozen fail-closed contract for sector details."""
    return JSONResponse(
        status_code=503,
        content=SectorDetailErrorResponse(
            error=SectorDetailErrorBody(code=code, message=message),
            meta=MarketMeta(
                status="failed",
                latency_ms=round((time.time() - started_at) * 1000),
                failed_sources=failed_sources,
            ),
        ).model_dump(mode="json"),
    )


def _market_limitations(items: list[IndexLimitation]) -> list[MarketLimitation]:
    return [MarketLimitation.model_validate(item.model_dump()) for item in items]


def _market_source_diagnostics(
    items: list[IndexSourceDiagnostic],
) -> list[MarketSourceDiagnostic]:
    return [MarketSourceDiagnostic.model_validate(item.model_dump()) for item in items]


def _board_snapshot_frame(kind: BoardKind) -> pd.DataFrame:
    """Adapt the frozen snapshot model to this router's internal tabular pipeline."""
    return _snapshot_frame(board_snapshots.fetch(kind))


def _snapshot_frame(snapshot: BoardSnapshot) -> pd.DataFrame:
    frame = pd.DataFrame([
        {
            "板块代码": quote.code,
            "板块名称": quote.name,
            "涨跌幅": quote.change_pct,
            "主力净流入-净额": (
                quote.fund_flow / 100_000_000 if quote.fund_flow is not None else None
            ),
            "数据时间": quote.as_of,
        }
        for quote in snapshot.quotes
    ])
    frame.attrs.update({
        "audited_snapshot": True,
        "cached": snapshot.cached,
        "fetched_at": snapshot.fetched_at,
        "possibly_delayed": snapshot.possibly_delayed,
        "source": snapshot.source,
    })
    return frame


def _fetch_single_board_snapshot(sector_id: str) -> tuple[BoardKind, pd.Series] | None:
    snapshot = board_snapshots.fetch_detail(sector_id)
    if snapshot is None:
        return None
    quote = snapshot.quote
    return snapshot.kind, pd.Series({
        "板块代码": snapshot.code, "板块名称": snapshot.name,
        "涨跌幅": quote.change_pct if quote is not None else None,
        "主力净流入-净额": (
            quote.fund_flow / 100_000_000
            if quote is not None and quote.fund_flow is not None else None
        ),
        "数据时间": quote.as_of if quote is not None else None,
    })


def _fetch_industry_board_snapshot() -> pd.DataFrame:
    return _board_snapshot_frame("industry")


def _fetch_concept_board_snapshot() -> pd.DataFrame:
    return _board_snapshot_frame("concept")


def _fetch_board_members_snapshot(sector_id: str, kind: BoardKind) -> pd.DataFrame:
    snapshot: BoardMembersSnapshot = board_snapshots.fetch_members(sector_id, kind)
    frame = pd.DataFrame([
        {
            "代码": member.code,
            "名称": member.name,
            "现价": member.price,
            "涨跌幅": member.change_pct,
            "主力净流入": (
                member.fund_flow / 100_000_000 if member.fund_flow is not None else None
            ),
            "数据时间": member.as_of,
        }
        for member in snapshot.members
    ])
    frame.attrs.update({
        "audited_snapshot": True,
        "cached": snapshot.cached,
        "fetched_at": snapshot.fetched_at,
        "possibly_delayed": snapshot.possibly_delayed,
        "source": snapshot.source,
    })
    return frame


def _nullable_board_number(value: object) -> float | None:
    missing = pd.isna(value)
    if isinstance(missing, bool) and missing:
        return None
    return safe_float(value)


BoardCallFailure = Literal["timeout", "failed"]


async def _fetch_board_dataframes(
    calls: dict[str, Callable[[], pd.DataFrame]],
    *,
    timeout: float,
) -> tuple[dict[str, pd.DataFrame], dict[str, BoardCallFailure]]:
    """Run board DataFrame calls concurrently under one aggregate deadline."""
    tasks = {
        call_id: asyncio.create_task(
            _sector_source_runner.run(call),
            name=f"market-board-{call_id}",
        )
        for call_id, call in calls.items()
    }
    try:
        done, pending = await asyncio.wait(tasks.values(), timeout=timeout)
    except asyncio.CancelledError:
        for task in tasks.values():
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks.values(), return_exceptions=True)
        raise
    if pending:
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    frames: dict[str, pd.DataFrame] = {}
    failures: dict[str, BoardCallFailure] = {}
    for call_id, task in tasks.items():
        if task not in done:
            logger.error("获取板块上游超时: call=%s timeout=%ss", call_id, timeout)
            failures[call_id] = "timeout"
            frames[call_id] = pd.DataFrame()
            continue
        try:
            frames[call_id] = task.result()
        except TimeoutError:
            logger.exception("板块上游返回超时: call=%s", call_id)
            failures[call_id] = "timeout"
            frames[call_id] = pd.DataFrame()
        except Exception:
            logger.exception("获取板块上游失败: call=%s", call_id)
            failures[call_id] = "failed"
            frames[call_id] = pd.DataFrame()
    return frames, failures


async def _fetch_board_perf_sources(
    *,
    timeout: float,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Fetch industry and concept rankings with stable source ordering."""
    frames, failures = await _fetch_board_dataframes(
        {
            "industry": _fetch_industry_board_snapshot,
            "concept": _fetch_concept_board_snapshot,
        },
        timeout=timeout,
    )
    return frames, list(failures)


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
        f"{board_name}（{'行业' if board_type == 'industry' else '概念'}板块）",
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
    lines.append("数据来源：东方财富行情快照")
    return "\n".join(lines)


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


async def _sina_sectors(sort: str, started_at: float) -> dict | JSONResponse:
    try:
        snapshot = await run_sync(sina_boards.fetch)
    except Exception:
        logger.exception("Sina alternative board collection failed")
        return _market_failed("MARKET_SECTORS_FAILED", "备用板块行情暂时不可用", started_at,
                              failed_sources=["sina"])
    items = [SectorItemResp(
        id=f"sina:{board.code}", name=board.name, category=board.category,
        change_pct=board.change_pct, fund_flow=None, net_flow=board.net_flow / 100_000_000,
        source="sina", service_updated_at=snapshot.service_updated_at,
        as_of=None, snapshot_may_be_delayed=True,
        top_stocks=[board.leader] if board.leader else [],
    ) for board in snapshot.boards]
    applied = sort if sort in ("change_pct", "net_flow") else "upstream_order"
    if applied == "change_pct":
        items.sort(key=lambda item: item.change_pct, reverse=True)
    elif applied == "net_flow":
        items.sort(key=lambda item: item.net_flow or 0, reverse=True)
    for rank, item in enumerate(items, 1):
        item.rank = rank
    limitations = [
        MarketLimitation(code="SINA_BOARD_BASIS",
                         message="新浪备用榜单：分类与东财不同，未跨源拼接涨跌幅；板块链接查看新浪来源"),
        MarketLimitation(code="FUND_FLOW_UNAVAILABLE",
                         message="新浪资金净流入不等于主力净流入，主力字段仍缺失"),
        MarketLimitation(code="SOURCE_SERVICE_TIME_ONLY", message=(
            f"资金服务更新时间 {snapshot.service_updated_at.isoformat()}；"
            "该时间不是逐板块行情时间，不能据此确认实时性")),
    ]
    return {"data": [item.model_dump() for item in items], "meta": _market_meta(
        "partial", started_at, cached=snapshot.cached, limitations=limitations,
        sort_requested=sort, sort_applied=applied,
    )}


@router.get(
    "/sectors",
    response_model=SectorsEnvelope,
    responses={503: {"model": MarketErrorResponse}},
)
async def get_sectors(
    sort: str = Query("fund_flow", description="排序维度"),
    source: Literal["eastmoney", "sina"] = Query("eastmoney"),
):
    """板块排行（行业 + 概念），含真实涨跌幅和资金流向"""
    t0 = time.time()
    if source == "sina":
        return await _sina_sectors(sort, t0)
    items: list[SectorItemResp] = []
    fund_flow_missing_sources: list[str] = []
    board_frames, failed_sources = await _fetch_board_perf_sources(
        timeout=DATA_TIMEOUT,
    )

    # Display-only recovery: never feed historical snapshots into detail/AI collectors.
    restored_kinds: list[str] = []
    store = board_snapshots.store
    if store is not None:
        for kind in ("industry", "concept"):
            if not board_frames[kind].empty:
                continue
            try:
                stored = await run_sync(store.load, f"boards:{kind}")
                if stored is not None and isinstance(stored.snapshot, BoardSnapshot):
                    board_frames[kind] = _snapshot_frame(
                        stored.snapshot.model_copy(update={"cached": True})
                    )
                    restored_kinds.append(kind)
                    if kind not in failed_sources:
                        failed_sources.append(kind)
            except Exception:
                logger.exception("Board display snapshot restore failed: category=%s", kind)

    audited_kinds: set[str] = set()
    snapshot_times: list[datetime] = []
    snapshot_cached = False

    # 行业板块
    df_ind = board_frames["industry"]
    if not df_ind.empty:
        if df_ind.attrs.get("audited_snapshot") is True:
            audited_kinds.add("industry")
            snapshot_cached = snapshot_cached or df_ind.attrs.get("cached") is True
        industry_has_fund_flow = "主力净流入-净额" in df_ind.columns
        if (
            not industry_has_fund_flow
            or bool(df_ind["主力净流入-净额"].isna().to_numpy().any())
        ):
            fund_flow_missing_sources.append("industry")
        for i, (_, row) in enumerate(df_ind.iterrows()):
            code = safe_str(row.get("板块代码", ""))
            name = safe_str(row.get("板块名称", ""))
            as_of = row.get("数据时间")
            if isinstance(as_of, datetime):
                snapshot_times.append(as_of)
            items.append(SectorItemResp(
                id=code, name=name, rank=i + 1,
                change_pct=safe_float(row.get("涨跌幅", 0.0)),
                fund_flow=(
                    _nullable_board_number(row.get("主力净流入-净额"))
                    if industry_has_fund_flow else None
                ),
                category="industry",
                as_of=as_of if isinstance(as_of, datetime) else None,
                snapshot_may_be_delayed=df_ind.attrs.get("possibly_delayed") is True,
            ))

    # 概念板块
    df_con = board_frames["concept"]
    if not df_con.empty:
        if df_con.attrs.get("audited_snapshot") is True:
            audited_kinds.add("concept")
            snapshot_cached = snapshot_cached or df_con.attrs.get("cached") is True
        concept_has_fund_flow = "主力净流入-净额" in df_con.columns
        if (
            not concept_has_fund_flow
            or bool(df_con["主力净流入-净额"].isna().to_numpy().any())
        ):
            fund_flow_missing_sources.append("concept")
        offset = len(items)
        for i, (_, row) in enumerate(df_con.iterrows()):
            code = safe_str(row.get("板块代码", ""))
            name = safe_str(row.get("板块名称", ""))
            as_of = row.get("数据时间")
            if isinstance(as_of, datetime):
                snapshot_times.append(as_of)
            items.append(SectorItemResp(
                id=code, name=name, rank=offset + i + 1,
                change_pct=safe_float(row.get("涨跌幅", 0.0)),
                fund_flow=(
                    _nullable_board_number(row.get("主力净流入-净额"))
                    if concept_has_fund_flow else None
                ),
                category="concept",
                as_of=as_of if isinstance(as_of, datetime) else None,
                snapshot_may_be_delayed=df_con.attrs.get("possibly_delayed") is True,
            ))

    if not items and failed_sources:
        return _market_failed(
            "MARKET_SECTORS_FAILED", "板块行情暂时不可用", t0,
            failed_sources=failed_sources,
        )
    limitations: list[MarketLimitation] = []
    if restored_kinds:
        limitations.append(MarketLimitation(
            code="BOARD_HISTORY_ONLY",
            message=("行情更新失败，当前包含上次成功的历史快照（"
                     + "、".join(restored_kinds)
                     + "）；排名仅反映所示数据时点，不代表当前行情，不用于实时决策"),
        ))
    if audited_kinds:
        as_of_min = min(snapshot_times).isoformat() if snapshot_times else "未知"
        as_of_max = max(snapshot_times).isoformat() if snapshot_times else "未知"
        time_range = as_of_min if as_of_min == as_of_max else f"{as_of_min} 至 {as_of_max}"
        limitations.append(MarketLimitation(
            code="BOARD_SNAPSHOT_MAY_BE_DELAYED",
            message=f"当前显示东方财富快照，可能延迟；数据时间 {time_range}",
        ))
    if "industry" in audited_kinds:
        limitations.append(MarketLimitation(
            code="BOARD_INDUSTRY_LEVELS_MIXED",
            message="行业结果包含东财一级、二级、三级行业，当前未按层级筛选",
        ))
        if not any(item.id == "BK1362" for item in items if item.category == "industry"):
            limitations.append(MarketLimitation(
                code="BOARD_CATALOG_QUOTE_MISSING",
                message="官方目录中的三级行业 BK1362 其他多元金融当前无报价，未补零",
            ))
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
        "stale" if restored_kinds else (
            "partial" if failed_sources or limitations else "success"
        )
    )
    return {
        "data": [i.model_dump() for i in items],
        "meta": _market_meta(
            status,
            t0,
            cached=snapshot_cached,
            failed_sources=failed_sources,
            limitations=limitations,
            sort_requested=sort,
            sort_applied=sort_applied,
        ),
    }


@router.get(
    "/sector/{sector_id:str}",
    response_model=SectorDetailEnvelope,
    responses={
        404: {"model": MarketErrorResponse},
        503: {"model": SectorDetailErrorResponse},
    },
)
async def get_sector_detail(sector_id: str):
    """板块详情 — 含成分股 + 热度 + AI 分析 + 产业链映射"""
    t0 = time.time()
    board_type: BoardKind | None = None
    try:
        async with asyncio.timeout(DATA_TIMEOUT):
            board_frames, board_failures = await _fetch_board_dataframes(
                {
                    "industry": _fetch_industry_board_snapshot,
                    "concept": _fetch_concept_board_snapshot,
                },
                timeout=DATA_TIMEOUT,
            )
            matches: list[tuple[BoardKind, pd.Series]] = []
            for kind in ("industry", "concept"):
                frame = board_frames[kind]
                if frame.empty:
                    continue
                matched = frame[frame["板块代码"].astype(str) == sector_id]
                if not matched.empty:
                    matches.append((kind, matched.iloc[0]))
            if not matches and board_failures:
                # Full rankings must not block an independently verified board.
                single = await _sector_source_runner.run(_fetch_single_board_snapshot, sector_id)
                if single is not None:
                    matches.append(single)
            if not matches:
                if board_failures:
                    failure_code = (
                        "MARKET_SECTOR_DETAIL_TIMEOUT"
                        if "timeout" in board_failures.values()
                        else "MARKET_SECTOR_DETAIL_FAILED"
                    )
                    return _sector_detail_failed(
                        failure_code,
                        "板块详情上游超时" if failure_code.endswith("TIMEOUT")
                        else "板块详情暂时不可用",
                        t0,
                        failed_sources=list(board_failures),
                    )
                return JSONResponse(
                    status_code=404,
                    content=MarketErrorResponse(
                        error=MarketErrorBody(
                            code="MARKET_SECTOR_NOT_FOUND", message="未找到该板块",
                        ),
                        meta=MarketMeta(
                            status="empty",
                            latency_ms=round((time.time() - t0) * 1000),
                        ),
                    ).model_dump(mode="json"),
                )
            if len(matches) != 1:
                raise ValueError("board identity appears in multiple categories")
            board_type, board_row = matches[0]
            stocks_df = await _sector_source_runner.run(
                _fetch_board_members_snapshot, sector_id, board_type,
            )
    except TimeoutError:
        logger.exception("板块详情聚合超时: sector_id=%s", sector_id)
        return _sector_detail_failed(
            "MARKET_SECTOR_DETAIL_TIMEOUT",
            "板块详情上游超时",
            t0,
            failed_sources=[board_type or "industry"],
        )
    except Exception:
        logger.exception("板块详情上游失败: sector_id=%s", sector_id)
        return _sector_detail_failed(
            "MARKET_SECTOR_DETAIL_FAILED",
            "板块详情暂时不可用",
            t0,
            failed_sources=[board_type or "industry"],
        )
    assert board_type is not None
    board_name = safe_str(board_row.get("板块名称", sector_id))
    board_as_of = board_row.get("数据时间")

    # 热度
    heat = _calc_heat(stocks_df)

    # 板块涨跌幅 + 资金流
    change_pct = _nullable_board_number(board_row.get("涨跌幅"))
    fund_flow = _nullable_board_number(board_row.get("主力净流入-净额"))

    # 成分股列表
    stocks: list[SectorStockResp] = []
    omitted_quote_count = 0
    if not stocks_df.empty:
        for _, row in stocks_df.iterrows():
            price = _nullable_board_number(row.get("现价"))
            stock_change = _nullable_board_number(row.get("涨跌幅"))
            if price is None or stock_change is None:
                omitted_quote_count += 1
                continue
            stocks.append(SectorStockResp(
                code=safe_str(row.get("代码", "")),
                name=safe_str(row.get("名称", "")),
                price=price, change_pct=stock_change,
                fund_flow=_nullable_board_number(row.get("主力净流入")),
                ai_rating=_calc_rating(stock_change),
            ))

    # AI 分析
    ai_analysis = _build_ai_analysis(board_name, stocks_df, heat, board_type)

    # 产业链映射
    chain_map = _build_chain_map(stocks_df, board_type)
    chain_evidence = None
    chain_error = False
    try:
        chain_evidence = get_sector_chain(sector_id, board_name)
    except (ValueError, OSError):
        chain_error = True
        logger.exception("产业链证据目录无效: sector_id=%s", sector_id)

    detail = SectorDetailResp(
        id=sector_id, name=board_name,
        change_pct=change_pct, fund_flow=fund_flow,
        heat=heat, stocks=stocks,
        ai_analysis=ai_analysis, chain_map=chain_map, chain_evidence=chain_evidence,
    )
    stock_time_values = stocks_df["数据时间"].tolist() if "数据时间" in stocks_df else []
    snapshot_times = [
        value for value in [board_as_of, *stock_time_values] if isinstance(value, datetime)
    ]
    as_of_min = min(snapshot_times).isoformat() if snapshot_times else "未知"
    as_of_max = max(snapshot_times).isoformat() if snapshot_times else "未知"
    time_range = as_of_min if as_of_min == as_of_max else f"{as_of_min} 至 {as_of_max}"
    limitations = [
        MarketLimitation(
            code="BOARD_SNAPSHOT_MAY_BE_DELAYED",
            message=f"当前显示东方财富快照，可能延迟；数据时间 {time_range}",
        ),

    ]
    if chain_evidence is None:
        limitations.append(MarketLimitation(
            code="CHAIN_EVIDENCE_INVALID" if chain_error else "CHAIN_MAP_UNAVAILABLE",
            message=("产业链资料校验失败，暂不展示" if chain_error
                     else "该板块尚未收录可核验的产业链资料"),
        ))
    if change_pct is None:
        limitations.append(MarketLimitation(
            code="BOARD_QUOTE_UNAVAILABLE",
            message="板块行情暂不可用，已展示核验名称和成分股；缺失指标暂无数据",
        ))
    stock_fund_flow_missing = (
        not stocks_df.empty
        and ("主力净流入" not in stocks_df.columns
             or bool(stocks_df["主力净流入"].isna().to_numpy().any()))
    )
    if fund_flow is None or stock_fund_flow_missing:
        limitations.append(MarketLimitation(
            code="FUND_FLOW_UNAVAILABLE",
            message="板块或部分成分股资金流未知，未知值返回 null",
        ))
    if omitted_quote_count:
        limitations.append(MarketLimitation(
            code="MEMBER_QUOTE_UNAVAILABLE",
            message=f"{omitted_quote_count}只成分股缺少价格或涨跌幅，未用0补值且未展示",
        ))
    if stocks_df.empty:
        limitations.append(MarketLimitation(
            code="BOARD_MEMBERS_EMPTY", message="当前板块没有可用成分股行情",
        ))
    return {
        "data": detail.model_dump(mode="json"),
        "meta": _market_meta(
            "partial", t0,
            cached=(board_frames[board_type].attrs.get("cached") is True
                    or stocks_df.attrs.get("cached") is True),
            limitations=limitations,
        ),
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
        df: pd.DataFrame = await run_sync(fetch_caixin_news)
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
