"""DP-006 镜子反思模块

辩论结束后产出一份历史对比报告（上次类似市况谁的判断准），
展示给用户看，不自动注入。

核心流程：
  1. 从 MemoryStore 查询历史辩论记录（("episodic", "debate") 命名空间）
  2. 从 MemoryStore 查询反思记录（("reflective", "debate") 命名空间）
  3. 通过 session_id 关联，提取每位大师的历史判断正确性
  4. 汇总统计并生成 MirrorReport

设计决策：
  · 纯统计计算，不调用 LLM
  · 只统计已有 actual_direction 的记录（即有 RC-002 回调数据的）
  · 数据不足时（< 2 条有实际结果的记录）不生成 summary
  · 与 TrustTracker 结合展示板块胜率

用法：
    from src.debate.mirror import generate_mirror_report

    report = await generate_mirror_report(
        stock_code="000001",
        stock_name="平安银行",
        current_analyses={...},  # 当前辩论的分析 dict
        memory_store=store,
        trust_tracker=tracker,
        sector="银行",
    )
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.debate.models import AgentAnalysis
    from src.debate.trust import TrustTracker
    from src.memory.store import MemoryStore

from src.debate.models import MirrorEntry, MirrorReport

logger = logging.getLogger(__name__)

_MIN_SUFFICIENT_SAMPLES = 2  # 最小有实际结果的记录数


async def generate_mirror_report(
    stock_code: str,
    stock_name: str = "",
    current_analyses: dict[str, AgentAnalysis] | None = None,
    memory_store: MemoryStore | None = None,
    trust_tracker: TrustTracker | None = None,
    sector: str = "",
    max_histories: int = 10,
) -> MirrorReport:
    """生成镜子反思报告

    查询历史辩论记录和反思记录，对比当前分析中各位大师在相似情境下的表现。

    Args:
        stock_code: 当前股票代码
        stock_name: 当前股票名称
        current_analyses: 当前辩论的分析结果 dict（用于提取大师名称）
        memory_store: 记忆存储（未提供时返回空报告）
        trust_tracker: 信任度追踪器（可选，用于板块胜率）
        sector: 板块标识（可选，用于筛选同板块记录）
        max_histories: 最多返回的历史记录条数

    Returns:
        MirrorReport — 无历史数据时字段为空
    """
    if memory_store is None:
        return MirrorReport(
            stock_code=stock_code,
            stock_name=stock_name,
            total_histories_found=0,
        )

    # ── 1. 查询历史辩论记录 ─────────────────────────────
    try:
        items = await memory_store.search(
            namespace=("episodic", "debate"),
            query="",
            k=50,
        )
    except Exception:
        logger.exception("镜子反思: 历史辩论记录查询失败")
        return MirrorReport(
            stock_code=stock_code,
            stock_name=stock_name,
            total_histories_found=0,
        )

    if not items:
        return MirrorReport(
            stock_code=stock_code,
            stock_name=stock_name,
            total_histories_found=0,
        )

    # ── 2. 查询历史反思记录（获取 actual_direction）─────────
    reflection_map: dict[str, dict] = {}
    try:
        ref_items = await memory_store.search(
            namespace=("reflective", "debate"),
            query="",
            k=50,
        )
        for item in ref_items:
            val = item.value if isinstance(item.value, dict) else {}
            sid = str(val.get("session_id", ""))
            if sid and val.get("actual_direction"):
                reflection_map[sid] = val
    except Exception:
        logger.exception("镜子反思: 反思记录查询失败")
        reflection_map = {}

    # ── 3. 筛选同股票 + 同板块记录 ──────────────────────
    same_stock_values: list[dict] = []
    sector_values: list[dict] = []

    for item in items:
        val = item.value if isinstance(item.value, dict) else {}
        code = str(val.get("stock_code", ""))
        if code == stock_code:
            same_stock_values.append(val)
        elif sector and str(val.get("sector", "")) == sector:
            sector_values.append(val)

    all_relevant = same_stock_values + sector_values
    if not all_relevant:
        return MirrorReport(
            stock_code=stock_code,
            stock_name=stock_name,
            total_histories_found=len(items),
        )

    # ── 4. 构建 MirrorEntry ─────────────────────────────
    same_stock_entries: list[MirrorEntry] = []
    sector_entries: list[MirrorEntry] = []

    for record in same_stock_values:
        entry = _build_mirror_entry(record, reflection_map)
        same_stock_entries.append(entry)

    for record in sector_values:
        entry = _build_mirror_entry(record, reflection_map)
        sector_entries.append(entry)

    # 按决策日期排序（最新的在前）
    same_stock_entries.sort(key=lambda e: e.decision_date, reverse=True)
    sector_entries.sort(key=lambda e: e.decision_date, reverse=True)

    # 限制数量
    same_stock_entries = same_stock_entries[:max_histories]
    sector_entries = sector_entries[:max_histories]

    # ── 5. 统计大师准确率 ───────────────────────────────
    # 5a. 从历史 master_results 统计
    masters_accuracy, masters_count = _compute_masters_accuracy_from_history(
        same_stock_entries + sector_entries,
    )

    # 5b. 用 TrustTracker 补充（只在历史统计不足时）
    if trust_tracker and current_analyses:
        for name in current_analyses:
            if name in masters_accuracy:
                continue  # 已有历史统计数据
            try:
                report = await trust_tracker.get_trust_report(name)
                if report and report.metrics.total_samples > 0:
                    masters_accuracy[name] = report.metrics.win_rate
                    masters_count[name] = report.metrics.total_samples
            except Exception:
                logger.debug("TrustTracker 查询失败: agent=%s", name)

    # ── 6. 判断数据是否充足 ─────────────────────────────
    entries_with_outcome = (
        [e for e in same_stock_entries if e.actual_direction is not None]
        + [e for e in sector_entries if e.actual_direction is not None]
    )
    data_sufficient = len(entries_with_outcome) >= _MIN_SUFFICIENT_SAMPLES

    # ── 7. 生成 summary ────────────────────────────────
    summary_lines: list[str] = []
    if data_sufficient:
        if same_stock_entries:
            correct = sum(
                1 for e in same_stock_entries if e.actual_direction and e.was_correct
            )
            total = sum(1 for e in same_stock_entries if e.actual_direction)
            if total > 0:
                summary_lines.append(
                    f"对 {stock_name}({stock_code}) 共有 {len(same_stock_entries)} "
                    f"次历史分析，{total} 次有实际结果，{correct}/{total} 判断正确。"
                )
        if masters_accuracy:
            top_master = max(masters_accuracy, key=masters_accuracy.get)  # type: ignore[arg-type]
            top_rate = masters_accuracy[top_master]
            summary_lines.append(
                f"在相似情境下最可靠的 Agent: {top_master} ({top_rate:.0%})"
            )
    else:
        summary_lines.append("历史数据不足，暂无法生成有效对比。")

    summary = "；".join(summary_lines)

    return MirrorReport(
        stock_code=stock_code,
        stock_name=stock_name,
        total_histories_found=len(items),
        same_stock_histories=same_stock_entries,
        sector_histories=sector_entries,
        masters_accuracy=masters_accuracy,
        masters_sample_count=masters_count,
        data_sufficient=data_sufficient,
        summary=summary,
    )


def _build_mirror_entry(
    record: dict,
    reflection_map: dict[str, dict],
) -> MirrorEntry:
    """从历史记录构建单个 MirrorEntry

    Args:
        record: episodic 命名空间中的一条历史决策 dict
        reflection_map: session_id → ReflectionRecord dict 的映射

    Returns:
        构建好的 MirrorEntry
    """
    session_id = str(record.get("session_id", ""))
    reflection = reflection_map.get(session_id)

    # 从反思记录获取实际结果
    actual_direction: str | None = None
    actual_price_change: float | None = None
    was_correct: bool | None = None

    if reflection is not None:
        actual_direction = str(reflection.get("actual_direction")) or None
        price_raw = reflection.get("actual_price_change_pct")
        actual_price_change = float(price_raw) if price_raw is not None else None
        was_correct = bool(reflection.get("was_correct", False))

    # 统计每位大师的方向正确性
    master_results: dict[str, bool | None] = {}
    analyses_summary = record.get("analyses_summary", [])
    for summary in analyses_summary:
        if isinstance(summary, dict):
            name = str(summary.get("agent_name", ""))
            if not name:
                continue
            direction = summary.get("direction", "")
            if actual_direction and direction in ("Bullish", "Bearish", "Neutral"):
                master_results[name] = direction == actual_direction
            else:
                master_results[name] = None

    return MirrorEntry(
        stock_code=str(record.get("stock_code", "")),
        stock_name=str(record.get("stock_name", "")),
        decision_date=str(record.get("decision_date", ""))[:10],
        consensus_direction=str(record.get("consensus", "Neutral")),
        consensus_confidence=float(record.get("confidence", 0.0)),
        actual_direction=actual_direction,
        actual_price_change_pct=actual_price_change,
        was_correct=was_correct,
        master_results=master_results,
    )


def _compute_masters_accuracy_from_history(
    all_entries: list[MirrorEntry],
) -> tuple[dict[str, float], dict[str, int]]:
    """从历史 MirrorEntry 的 master_results 统计每位大师的准确率

    Args:
        all_entries: 所有相关历史 MirrorEntry

    Returns:
        (masters_accuracy, masters_sample_count)
    """
    agent_correct: dict[str, int] = {}
    agent_total: dict[str, int] = {}
    masters_accuracy: dict[str, float] = {}
    masters_count: dict[str, int] = {}

    for entry in all_entries:
        for name, is_correct in entry.master_results.items():
            if is_correct is not None:
                agent_total[name] = agent_total.get(name, 0) + 1
                if is_correct:
                    agent_correct[name] = agent_correct.get(name, 0) + 1

    for name in agent_total:
        if agent_total[name] >= _MIN_SUFFICIENT_SAMPLES:
            masters_accuracy[name] = agent_correct.get(name, 0) / agent_total[name]
            masters_count[name] = agent_total[name]

    return masters_accuracy, masters_count


__all__ = [
    "MirrorEntry",
    "MirrorReport",
    "generate_mirror_report",
]
