"""信任度路由 —— /api/trust/*

提供大师信任度报告查询和排行榜。
接入 src/debate/trust.py 的 TrustTracker 进行真实数据查询。
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("backend.trust")
router = APIRouter(prefix="/api/trust")


# ── 响应模型 ──────────────────────────────────────────────────


class TrustReportResp(BaseModel):
    """信任度报告（对齐前端 TrustReport 类型）

    由 src.debate.trust.TrustReport 映射而来，仅暴露前端需要的字段。
    """

    agent_name: str = ""
    win_rate: float = 0.0
    brier_score: float = 0.0
    confidence_bias: float = 0.0
    trend_direction: str = "stable"
    total_predictions: int = 0
    is_reliable: bool = False
    summary: str = ""


# ── 惰性导入 + 单例 ──────────────────────────────────────────


def _get_tracker():
    """惰性创建 TrustTracker 实例

    使用 JsonFileStore 持久化，数据存储于 data/memory/trust/ 下。
    避免导入时触发 torch 等重型依赖。
    """
    from src.debate.trust import TrustTracker  # noqa: PLC0415
    from src.memory.store import JsonFileStore  # noqa: PLC0415

    store = JsonFileStore(base_path="data/memory")
    return TrustTracker(memory_store=store)


def _trust_report_to_resp(report: object) -> TrustReportResp:
    """将 src.debate.trust.TrustReport 映射为前端响应格式

    Args:
        report: TrustTracker.get_trust_report() 返回的 TrustReport 对象

    Returns:
        映射后的 TrustReportResp
    """
    agent_name = getattr(report, "agent_name", "")
    metrics = getattr(report, "metrics", None)
    summary = getattr(report, "summary", "")
    is_reliable = getattr(report, "is_reliable", False)

    if metrics is None:
        return TrustReportResp(
            agent_name=agent_name,
            summary=summary or "暂无信任度数据",
        )

    return TrustReportResp(
        agent_name=agent_name,
        win_rate=round(getattr(metrics, "win_rate", 0.0), 3),
        brier_score=round(getattr(metrics, "brier_score", 0.0), 4),
        confidence_bias=round(getattr(metrics, "confidence_bias", 0.0), 4),
        trend_direction=getattr(metrics, "trend_direction", "stable"),
        total_predictions=getattr(metrics, "total_samples", 0),
        is_reliable=is_reliable,
        summary=summary,
    )


# ── 路由 ──────────────────────────────────────────────────────


@router.get("/report/{agent_name:str}")
async def get_trust_report(agent_name: str):
    """查询指定大师的信任度报告"""
    t0 = time.time()
    try:
        tracker = _get_tracker()
        report = await tracker.get_trust_report(agent_name)
        resp = _trust_report_to_resp(report)
        return {
            "data": resp.model_dump(),
            "meta": {"latency_ms": round((time.time() - t0) * 1000)},
        }
    except Exception:
        logger.exception("获取信任度报告失败: agent=%s", agent_name)
        raise HTTPException(status_code=503, detail="查询信任度报告失败，数据源暂时不可用")


@router.get("/leaderboard")
async def get_trust_leaderboard():
    """信任度排行榜（按 win_rate 降序）"""
    t0 = time.time()
    try:
        tracker = _get_tracker()
        names = await tracker.get_all_agent_names()

        reports: list[TrustReportResp] = []
        for name in names:
            report = await tracker.get_trust_report(name)
            reports.append(_trust_report_to_resp(report))

        # 按 win_rate 降序（有数据的排前面）
        reports.sort(
            key=lambda r: (
                r.total_predictions > 0,
                r.win_rate,
            ),
            reverse=True,
        )

        return {
            "data": [r.model_dump() for r in reports],
            "meta": {"latency_ms": round((time.time() - t0) * 1000)},
        }
    except Exception:
        logger.exception("获取信任度排行榜失败")
        raise HTTPException(status_code=503, detail="获取信任度排行榜失败，数据源暂时不可用")
