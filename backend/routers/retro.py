"""复盘路由 —— /api/retro/*

提供复盘记录查询、聚合统计、用户操作记录等接口。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger("backend.retro")
router = APIRouter(prefix="/api/retro")


# ── 请求体模型 ────────────────────────────────────────────────


class ActionUpdateRequest(BaseModel):
    """更新用户操作"""
    action: str  # buy / sell / hold / skip


class OutcomeUpdateRequest(BaseModel):
    """更新实际结果"""
    return_pct: float
    price: float


# ── 惰性 store ────────────────────────────────────────────────


_store: Any = None


def _get_store():
    """惰性创建 RetroStore 单例"""
    global _store
    if _store is None:
        from src.retro.store import RetroStore  # noqa: PLC0415
        _store = RetroStore()
    return _store


def _record_to_dict(record: object) -> dict[str, Any]:
    """将 RetroRecord 转换为可序列化字典"""
    r = record
    return {
        "record_id": getattr(r, "record_id", ""),
        "session_id": getattr(r, "session_id", ""),
        "stock_code": getattr(r, "stock_code", ""),
        "stock_name": getattr(r, "stock_name", ""),
        "created_at": (
            getattr(r, "created_at").isoformat()
            if hasattr(r, "created_at") and getattr(r, "created_at")
            else ""
        ),
        "debate_latency_ms": getattr(r, "debate_latency_ms", 0.0),
        "consensus": getattr(r, "consensus", ""),
        "weighted_score": getattr(r, "weighted_score", 0.0),
        "confidence": getattr(r, "confidence", 0.0),
        "direction_distribution": getattr(r, "direction_distribution", {}),
        "avg_score": getattr(r, "avg_score", 0.0),
        "rating_distribution": getattr(r, "rating_distribution", {}),
        "price_at_debate": getattr(r, "price_at_debate"),
        "user_action": getattr(r, "user_action"),
        "user_action_at": (
            getattr(r, "user_action_at").isoformat()
            if hasattr(r, "user_action_at") and getattr(r, "user_action_at")
            else None
        ),
        "actual_return_pct": getattr(r, "actual_return_pct"),
        "actual_price": getattr(r, "actual_price"),
        "outcome": getattr(r, "outcome", "pending"),
        "notes": getattr(r, "notes", ""),
    }


# ── 路由 ──────────────────────────────────────────────────────


@router.get("/records")
async def list_records(
    stock_code: str | None = Query(None),
    outcome: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """查询复盘记录列表（按时间降序）"""
    try:
        store = _get_store()
        records = await store.list_records(
            stock_code=stock_code,
            outcome=outcome,
            limit=limit,
            offset=offset,
        )
        return {
            "data": [_record_to_dict(r) for r in records],
            "meta": {"total": len(records), "limit": limit, "offset": offset},
        }
    except Exception:
        logger.exception("查询复盘记录失败")
        raise HTTPException(status_code=500, detail="查询复盘记录失败")


@router.get("/summary")
async def get_summary():
    """获取复盘聚合统计"""
    try:
        store = _get_store()
        summary = await store.get_summary()
        return {
            "data": {
                "total_records": summary.total_records,
                "today_records": summary.today_records,
                "closed_records": summary.closed_records,
                "win_count": summary.win_count,
                "loss_count": summary.loss_count,
                "win_rate": summary.win_rate,
                "avg_confidence": summary.avg_confidence,
                "avg_score": summary.avg_score,
                "last_record_at": (
                    summary.last_record_at.isoformat()
                    if summary.last_record_at
                    else None
                ),
            }
        }
    except Exception:
        logger.exception("获取复盘统计失败")
        raise HTTPException(status_code=500, detail="获取复盘统计失败")


@router.put("/{record_id}/action")
async def update_action(record_id: str, req: ActionUpdateRequest):
    """记录用户操作"""
    if req.action not in ("buy", "sell", "hold", "skip"):
        raise HTTPException(status_code=422, detail="无效操作，须为 buy/sell/hold/skip")

    try:
        store = _get_store()
        record = await store.update_action(record_id, req.action)
        if record is None:
            raise HTTPException(status_code=404, detail="记录不存在")
        return {"data": _record_to_dict(record)}
    except HTTPException:
        raise
    except Exception:
        logger.exception("更新用户操作失败: record=%s", record_id)
        raise HTTPException(status_code=500, detail="更新用户操作失败")


@router.put("/{record_id}/outcome")
async def update_outcome(record_id: str, req: OutcomeUpdateRequest):
    """更新实际结果（手动录入）"""
    try:
        store = _get_store()
        record = await store.update_outcome(
            record_id=record_id,
            actual_return_pct=req.return_pct,
            actual_price=req.price,
        )
        if record is None:
            raise HTTPException(status_code=404, detail="记录不存在")
        return {"data": _record_to_dict(record)}
    except HTTPException:
        raise
    except Exception:
        logger.exception("更新实际结果失败: record=%s", record_id)
        raise HTTPException(status_code=500, detail="更新实际结果失败")


@router.post("/refresh")
async def refresh_pending():
    """刷新所有 pending 记录的实际涨跌幅

    对每个 pending 记录，获取当前行情价，
    与 debate 时价格比较，自动判定 outcome。
    """
    try:
        store = _get_store()
        from src.data.collector import DataCollector  # noqa: PLC0415

        collector = DataCollector()

        all_records = await store.list_records(outcome="pending")
        updated = 0
        errors = 0

        for record in all_records:
            if record.price_at_debate is None or record.price_at_debate == 0:
                continue
            try:
                quote = collector.get_realtime_quote(record.stock_code)
                if quote is None:
                    continue
                current_price = float(quote.price)

                if current_price <= 0:
                    continue

                return_pct = (current_price - record.price_at_debate) / record.price_at_debate
                await store.update_outcome(
                    record_id=record.record_id,
                    actual_return_pct=round(return_pct * 100, 4),
                    actual_price=current_price,
                )
                updated += 1
            except Exception:
                errors += 1
                continue

        return {
            "data": {
                "total_pending": len(all_records),
                "updated": updated,
                "errors": errors,
            }
        }
    except Exception:
        logger.exception("批量刷新复盘失败")
        raise HTTPException(status_code=500, detail="批量刷新复盘失败")


@router.delete("/{record_id}")
async def delete_record(record_id: str):
    """删除一条复盘记录"""
    try:
        store = _get_store()
        ok = await store.delete(record_id)
        if not ok:
            raise HTTPException(status_code=404, detail="记录不存在")
        return {"data": {"deleted": True}}
    except HTTPException:
        raise
    except Exception:
        logger.exception("删除复盘记录失败: record=%s", record_id)
        raise HTTPException(status_code=500, detail="删除复盘记录失败")
