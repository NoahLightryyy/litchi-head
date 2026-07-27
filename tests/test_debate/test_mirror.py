"""DP-006 镜子反思单元测试

测试策略：
1. generate_mirror_report 核心逻辑
   - 无历史记录 → 空报告
   - 有同股票历史 + 有 actual_direction → 正确统计
   - 历史记录有但无 actual_direction → 跳过统计
   - 样本不足 2 条 → data_sufficient=False
   - memory_store=None → 空报告安全降级
2. MirrorEntry / MirrorReport 模型验证
3. _build_mirror_entry 历史记录解析
4. 在 orchestrator graph 中的集成（make_mirror_node）
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.debate.mirror import (
    _build_mirror_entry,
    _compute_masters_accuracy_from_history,
    generate_mirror_report,
)
from src.debate.models import AgentAnalysis, MirrorEntry, MirrorReport
from src.memory.store import MemoryItem, MemoryStore

# ═══════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════


def _episodic_item(
    stock_code: str = "000001",
    stock_name: str = "平安银行",
    session_id: str = "session-001",
    consensus: str = "Bullish",
    confidence: float = 0.8,
    decision_date: str = "2026-07-20",
    analyses_summary: list | None = None,
) -> MemoryItem:
    """创建一条模拟的 episodic 辩论记录"""
    if analyses_summary is None:
        analyses_summary = [
            {
                "agent_name": "master.buffett",
                "direction": "Bullish", "score": 80, "confidence": 0.85,
            },
            {
                "agent_name": "master.munger",
                "direction": "Bearish", "score": 40, "confidence": 0.6,
            },
        ]
    return MemoryItem(
        key=stock_code,
        value={
            "stock_code": stock_code,
            "stock_name": stock_name,
            "session_id": session_id,
            "decision_date": decision_date,
            "consensus": consensus,
            "confidence": confidence,
            "analyses_summary": analyses_summary,
        },
        namespace=("episodic", "debate"),
    )


def _reflective_item(
    session_id: str = "session-001",
    actual_direction: str = "Bullish",
    price_change: float = 3.5,
    was_correct: bool = True,
) -> MemoryItem:
    """创建一条模拟的 reflective 反思记录"""
    return MemoryItem(
        key=session_id,
        value={
            "session_id": session_id,
            "actual_direction": actual_direction,
            "actual_price_change_pct": price_change,
            "was_correct": was_correct,
        },
        namespace=("reflective", "debate"),
    )


def _mock_store(
    episodic_items: list | None = None,
    reflective_items: list | None = None,
) -> AsyncMock:
    """创建模拟的 MemoryStore

    Args:
        episodic_items: search 返回的历史辩论记录列表
        reflective_items: search 返回的反思记录列表

    Returns:
        配置好的 AsyncMock
    """
    mock = AsyncMock(spec=MemoryStore)

    async def search_side_effect(namespace=(), **kwargs):
        if namespace == ("episodic", "debate"):
            return episodic_items or []
        if namespace == ("reflective", "debate"):
            return reflective_items or []
        return []

    mock.search.side_effect = search_side_effect
    return mock


def _make_analysis(
    agent_name: str = "master.buffett",
    direction: str = "Bullish",
    score: int = 75,
    confidence: float = 0.8,
) -> AgentAnalysis:
    """快速构造 AgentAnalysis"""
    return AgentAnalysis(
        agent_name=agent_name,
        skill_id=agent_name.replace("master.", ""),
        skill_name=agent_name.split(".")[-1].title(),
        rating="看涨" if direction == "Bullish" else "看跌",
        score=score,
        summary="测试分析",
        analysis="...",
        key_evidence=["证据1"],
        confidence=confidence,
        success=True,
        direction=direction,
    )


# ═══════════════════════════════════════════════════════════════════
# MirrorEntry / MirrorReport 模型验证
# ═══════════════════════════════════════════════════════════════════


class TestMirrorModels:
    """MirrorEntry 和 MirrorReport 数据模型验证"""

    def test_mirror_entry_defaults(self):
        """MirrorEntry 默认值正确"""
        entry = MirrorEntry(stock_code="000001")
        assert entry.stock_code == "000001"
        assert entry.stock_name == ""
        assert entry.consensus_direction == "Neutral"
        assert entry.actual_direction is None
        assert entry.was_correct is None
        assert entry.master_results == {}

    def test_mirror_entry_full(self):
        """MirrorEntry 全字段构造"""
        entry = MirrorEntry(
            stock_code="000001",
            stock_name="平安银行",
            decision_date="2026-07-20",
            consensus_direction="Bullish",
            consensus_confidence=0.8,
            actual_direction="Bearish",
            actual_price_change_pct=-2.5,
            was_correct=False,
            master_results={"master.buffett": True, "master.munger": False},
        )
        assert entry.actual_direction == "Bearish"
        assert entry.was_correct is False
        assert entry.master_results["master.buffett"] is True

    def test_mirror_report_defaults(self):
        """MirrorReport 默认值正确"""
        report = MirrorReport(stock_code="000001")
        assert report.total_histories_found == 0
        assert report.data_sufficient is False
        assert report.summary == ""
        assert report.same_stock_histories == []
        assert report.masters_accuracy == {}


# ═══════════════════════════════════════════════════════════════════
# _build_mirror_entry 测试
# ═══════════════════════════════════════════════════════════════════


class TestBuildMirrorEntry:
    """_build_mirror_entry 历史记录解析"""

    def test_build_with_reflection(self):
        """有反思记录时正确获取 actual_direction"""
        record = _episodic_item().value
        reflection_map = {
            "session-001": {
                "actual_direction": "Bullish",
                "actual_price_change_pct": 3.5,
                "was_correct": True,
            }
        }
        entry = _build_mirror_entry(record, reflection_map)
        assert entry.actual_direction == "Bullish"
        assert entry.actual_price_change_pct == 3.5
        assert entry.was_correct is True
        # master.buffett Bullish == actual Bullish → True
        assert entry.master_results["master.buffett"] is True
        # master.munger Bearish != actual Bullish → False
        assert entry.master_results["master.munger"] is False

    def test_build_without_reflection(self):
        """无反思记录时 actual_direction 为 None"""
        record = _episodic_item().value
        entry = _build_mirror_entry(record, {})
        assert entry.actual_direction is None
        assert entry.was_correct is None
        # 无 actual_direction 时 master_results 全为 None
        assert entry.master_results["master.buffett"] is None
        assert entry.master_results["master.munger"] is None

    def test_build_wrong_prediction(self):
        """大师预测方向与实际不符时正确标记"""
        # master.buffett 看涨 (Bullish) vs 实际跌 (Bearish)
        record = _episodic_item().value
        reflection_map = {
            "session-001": {
                "actual_direction": "Bearish",
                "actual_price_change_pct": -2.0,
                "was_correct": False,
            }
        }
        entry = _build_mirror_entry(record, reflection_map)
        assert entry.actual_direction == "Bearish"
        assert entry.was_correct is False
        assert entry.master_results["master.buffett"] is False  # Bullish != Bearish


# ═══════════════════════════════════════════════════════════════════
# _compute_masters_accuracy_from_history 测试
# ═══════════════════════════════════════════════════════════════════


class TestComputeAccuracy:
    """大师准确率统计"""

    def test_compute_accuracy_basic(self):
        """正确统计每位大师的准确率"""
        entries = [
            MirrorEntry(
                stock_code="000001",
                actual_direction="Bullish",
                master_results={
                    "master.buffett": True,
                    "master.munger": False,
                },
            ),
            MirrorEntry(
                stock_code="000001",
                actual_direction="Bearish",
                master_results={
                    "master.buffett": False,
                    "master.munger": True,
                },
            ),
        ]
        accuracy, count = _compute_masters_accuracy_from_history(entries)
        assert accuracy["master.buffett"] == 0.5  # 1/2
        assert count["master.buffett"] == 2
        assert accuracy["master.munger"] == 0.5  # 1/2

    def test_compute_accuracy_skip_none(self):
        """无实际结果的 master_result 被跳过"""
        entries = [
            MirrorEntry(
                stock_code="000001",
                actual_direction=None,
                master_results={
                    "master.buffett": None,  # 无数据
                    "master.munger": True,
                },
            ),
        ]
        accuracy, count = _compute_masters_accuracy_from_history(entries)
        # buffett 只有 None 被跳过
        assert "master.buffett" not in accuracy
        # munger 样本不足 2 条也被排除
        assert "master.munger" not in accuracy

    def test_compute_accuracy_insufficient(self):
        """样本 < _MIN_SUFFICIENT_SAMPLES(2) 时不纳入统计"""
        entries = [
            MirrorEntry(
                stock_code="000001",
                actual_direction="Bullish",
                master_results={"master.buffett": True},
            ),
        ]
        accuracy, count = _compute_masters_accuracy_from_history(entries)
        assert "master.buffett" not in accuracy  # 只有 1 个样本


# ═══════════════════════════════════════════════════════════════════
# generate_mirror_report 核心逻辑
# ═══════════════════════════════════════════════════════════════════


class TestGenerateMirrorReport:
    """generate_mirror_report 主逻辑"""

    @pytest.mark.asyncio
    async def test_no_memory_store(self):
        """memory_store=None → 空报告"""
        report = await generate_mirror_report(stock_code="000001")
        assert report.total_histories_found == 0
        assert report.data_sufficient is False

    @pytest.mark.asyncio
    async def test_no_histories(self):
        """无历史记录 → total_histories_found=0"""
        mock_store = _mock_store(episodic_items=[])
        report = await generate_mirror_report(
            stock_code="000001", memory_store=mock_store,
        )
        assert report.total_histories_found == 0
        assert report.data_sufficient is False

    @pytest.mark.asyncio
    async def test_no_relevant_histories(self):
        """有历史记录但非同股票 → same_stock_histories 为空"""
        items = [_episodic_item(stock_code="600519", stock_name="贵州茅台")]
        mock_store = _mock_store(episodic_items=items)
        report = await generate_mirror_report(
            stock_code="000001", stock_name="平安银行",
            memory_store=mock_store,
        )
        assert report.total_histories_found == 1  # 确实查到了一条
        assert len(report.same_stock_histories) == 0

    @pytest.mark.asyncio
    async def test_same_stock_with_outcome(self):
        """同股票历史 + 有 actual_direction → 正确统计"""
        episodic = [
            _episodic_item(
                stock_code="000001",
                session_id="s1",
                consensus="Bullish",
                analyses_summary=[
                    {"agent_name": "master.buffett", "direction": "Bullish"},
                    {"agent_name": "master.munger", "direction": "Neutral"},
                ],
            ),
        ]
        reflective = [
            _reflective_item(session_id="s1", actual_direction="Bullish", was_correct=True),
        ]
        mock_store = _mock_store(episodic_items=episodic, reflective_items=reflective)
        report = await generate_mirror_report(
            stock_code="000001", stock_name="平安银行",
            memory_store=mock_store,
        )
        assert report.total_histories_found == 1
        assert len(report.same_stock_histories) == 1
        assert len(report.sector_histories) == 0
        entry = report.same_stock_histories[0]
        assert entry.actual_direction == "Bullish"
        assert entry.was_correct is True
        # data_sufficient = False 因为只有 1 条有实际结果（< 2）
        assert report.data_sufficient is False

    @pytest.mark.asyncio
    async def test_sufficient_samples(self):
        """有 ≥2 条有实际结果的记录 → data_sufficient=True"""
        episodic = [
            _episodic_item(
                stock_code="000001", session_id="s1",
                consensus="Bullish", decision_date="2026-07-20",
                analyses_summary=[
                    {"agent_name": "master.buffett", "direction": "Bullish"},
                ],
            ),
            _episodic_item(
                stock_code="000001", session_id="s2",
                consensus="Bearish", decision_date="2026-07-21",
                analyses_summary=[
                    {"agent_name": "master.buffett", "direction": "Bearish"},
                ],
            ),
        ]
        reflective = [
            _reflective_item(session_id="s1", actual_direction="Bullish", was_correct=True),
            _reflective_item(session_id="s2", actual_direction="Bearish", was_correct=True),
        ]
        mock_store = _mock_store(episodic_items=episodic, reflective_items=reflective)
        report = await generate_mirror_report(
            stock_code="000001", stock_name="平安银行",
            memory_store=mock_store,
            current_analyses={"master.buffett": _make_analysis()},
        )
        assert report.data_sufficient is True
        assert report.summary != ""
        assert "master.buffett" in report.masters_accuracy
        assert report.masters_accuracy["master.buffett"] == 1.0  # 2/2 正确

    @pytest.mark.asyncio
    async def test_sector_filtering(self):
        """提供 sector 时筛选同板块记录"""
        episodic = [
            _episodic_item(stock_code="000001", stock_name="平安银行"),
        ]
        # sector 不同 → 不会被 sector_histories 包含
        mock_store = _mock_store(episodic_items=episodic)
        report = await generate_mirror_report(
            stock_code="600519", stock_name="贵州茅台",
            memory_store=mock_store,
            sector="白酒",
        )
        assert len(report.same_stock_histories) == 0  # 不同股票
        assert len(report.sector_histories) == 0  # 不同板块
        assert report.total_histories_found == 1

    @pytest.mark.asyncio
    async def test_search_failure_returns_empty(self):
        """search 异常时安全降级返回空报告"""
        mock_store = AsyncMock(spec=MemoryStore)
        mock_store.search.side_effect = OSError("disk full")
        report = await generate_mirror_report(
            stock_code="000001", memory_store=mock_store,
        )
        assert report.total_histories_found == 0

    @pytest.mark.asyncio
    async def test_partial_master_data(self):
        """部分大师有历史数据、部分无 — masters_accuracy 只列有数据的"""
        episodic = [
            _episodic_item(
                stock_code="000001", session_id="s1",
                analyses_summary=[
                    {"agent_name": "master.buffett", "direction": "Bullish"},
                    {"agent_name": "master.munger", "direction": "Bearish"},
                ],
            ),
            _episodic_item(
                stock_code="000001", session_id="s2",
                analyses_summary=[
                    {"agent_name": "master.buffett", "direction": "Bullish"},
                    {"agent_name": "master.graham", "direction": "Neutral"},
                ],
            ),
        ]
        reflective = [
            _reflective_item(
                session_id="s1", actual_direction="Bullish", was_correct=True
            ),
            _reflective_item(
                session_id="s2", actual_direction="Bearish", was_correct=False
            ),
        ]
        mock_store = _mock_store(episodic_items=episodic, reflective_items=reflective)
        report = await generate_mirror_report(
            stock_code="000001",
            memory_store=mock_store,
            current_analyses={
                "master.buffett": _make_analysis(),
                "master.munger": _make_analysis(),
                "master.graham": _make_analysis(),
            },
        )
        # buffet 2 条, munger 1 条, graham 1 条 → 只有 buffet ≥ 2
        assert "master.buffett" in report.masters_accuracy
        assert report.masters_accuracy["master.buffett"] == 0.5  # 1/2
        assert "master.munger" not in report.masters_accuracy  # 样本不足
        assert "master.graham" not in report.masters_accuracy  # 样本不足


# ═══════════════════════════════════════════════════════════════════
# make_mirror_node 集成测试
# ═══════════════════════════════════════════════════════════════════


class TestMirrorNode:
    """make_mirror_node 集成"""

    @pytest.mark.asyncio
    async def test_mirror_node_no_store(self):
        """memory_store=None → mirror_node 返回空 dict"""
        from src.debate.orchestrator import make_mirror_node

        node = make_mirror_node(memory_store=None)
        result = await node({
            "debate_input": {"stock_code": "000001", "stock_name": "平安银行"},
            "analyses": {},
        })
        assert "mirror_report" in result
        # 空 dict 表示无数据
        assert result["mirror_report"] == {}

    @pytest.mark.asyncio
    async def test_mirror_node_with_data(self):
        """有数据时 mirror_node 返回正确报告"""
        from src.debate.orchestrator import make_mirror_node

        episodic = [
            _episodic_item(session_id="s1"),
        ]
        reflective = [
            _reflective_item(session_id="s1", actual_direction="Bullish", was_correct=True),
        ]
        mock_store = _mock_store(episodic_items=episodic, reflective_items=reflective)

        node = make_mirror_node(memory_store=mock_store)
        result = await node({
            "debate_input": {"stock_code": "000001", "stock_name": "平安银行"},
            "analyses": {},
        })
        report_dict = result["mirror_report"]
        # 验证序列化内容
        assert isinstance(report_dict, dict)
        assert report_dict.get("total_histories_found", 0) == 1
        assert len(report_dict.get("same_stock_histories", [])) == 1
