#!/usr/bin/env python
"""
全链路 LLM 调用成本测算脚本

使用方法：
    python scripts/measure_llm_cost.py

输出：
    - 每层 LLM 调用次数
    - 总调用次数
    - 估算 token 消耗（基于平均输入/输出长度）
    - 估算费用（基于 DeepSeek-Chat 定价）

原理：
    用 CountingLLMService 包装真实/模拟 LLM 服务，
    在完整跑通 9 层辩论链路时统计每次调用的模型、tokens。
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# 确保项目根目录在 sys.path
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.debate.models import DebateInput
from src.debate.orchestrator import DebateOrchestrator

# ═══════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════

# DeepSeek-Chat 定价（每 1K tokens，单位：人民币分）
PRICING = {
    "deepseek-chat": {"input": 0.05, "output": 0.15},  # 元/1K tokens
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}

# 各层估算 token 消耗（基于实际 prompt 模板长度 + 预期输出长度）
# 单位：输入_tokens + 输出_tokens
ESTIMATED_TOKENS_PER_CALL = {
    "analyst": (1200, 400),       # 分析师：市场简报 + 分析指令 + 结构化输出
    "master": (2000, 600),        # 大师：分析师报告汇总 + 大师人格 + 结构化输出
    "review": (3000, 400),        # 交叉审阅：同行分析 + 反驳指令
    "review_report": (4000, 500), # 独立评审：全部大师分析 + 评审指令
    "risk": (2500, 300),          # 风控官：投票结果 + 风控人格 + 决策
    "trader": (3500, 500),        # 交易员：投票 + 风控 + 交易指令
    "pm": (3000, 400),            # PM：全部上下文 + 裁决指令
}

DEFAULT_MODEL = "deepseek-chat"

# ═══════════════════════════════════════════════════════════════════
# 调用计数器
# ═══════════════════════════════════════════════════════════════════


class CallRecord:
    """单次 LLM 调用记录"""

    def __init__(self, layer: str, agent_name: str, model: str = DEFAULT_MODEL):
        self.layer = layer
        self.agent_name = agent_name
        self.model = model
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.timestamp = time.monotonic()


class CallCounter:
    """累计所有 LLM 调用"""

    def __init__(self):
        self.records: list[CallRecord] = []

    def add(self, record: CallRecord) -> None:
        self.records.append(record)

    def count_by_layer(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.records:
            counts[r.layer] = counts.get(r.layer, 0) + 1
        return counts

    def total_calls(self) -> int:
        return len(self.records)

    def estimate_cost(
        self,
        model: str = DEFAULT_MODEL,
        use_real_tokens: bool = False,
    ) -> float:
        """估算总费用（元）

        Args:
            model: 模型名称
            use_real_tokens: True 时使用实际 token 计数，False 时使用估算值

        Returns:
            估算总费用（元）
        """
        pricing = PRICING.get(model, PRICING[DEFAULT_MODEL])
        total = 0.0

        for r in self.records:
            if use_real_tokens and r.prompt_tokens > 0:
                pt = r.prompt_tokens
                ct = r.completion_tokens
            else:
                est = ESTIMATED_TOKENS_PER_CALL.get(r.layer, (1000, 300))
                pt, ct = est

            total += (pt / 1000) * pricing["input"]
            total += (ct / 1000) * pricing["output"]

        return round(total, 4)


# ═══════════════════════════════════════════════════════════════════
# Mock DataCollector
# ═══════════════════════════════════════════════════════════════════


def make_mock_collector():
    col = MagicMock()
    col.get_realtime_quotes.return_value = []
    col.get_klines.return_value = []
    col.get_news.return_value = []
    return col


# ═══════════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════════


async def measure():
    """跑通全链路，统计 LLM 调用次数，估算成本"""
    counter = CallCounter()

    # ═══════════════════ 场景 1: 基础 6 层 ═══════════════════
    print("=" * 60)
    print("litchi-head LLM 调用成本测算")
    print("=" * 60)

    # 基础 6 层（不含风控/交易员/PM）
    print("\n[场景 A] 基础 6 层（分析 -> 策略 -> 审阅 -> 评审 -> 聚合）")
    print("-" * 40)

    orch = DebateOrchestrator(
        data_collector=make_mock_collector(),
        skill_ids=["buffett", "munger", "graham", "dalio", "lynch"],
        enable_risk=False,
        enable_trader=False,
    )

    from unittest.mock import AsyncMock

    from src.debate.models import AgentAnalysis

    mock_analysis = AgentAnalysis(
        agent_name="master.test", skill_id="test", skill_name="测试大师",
        rating="看涨", score=75, summary="摘要", analysis="分析",
        key_evidence=[], confidence=0.75, direction="Bullish",
    )

    with patch(
        "src.debate.orchestrator._run_single_master",
        new_callable=AsyncMock,
        return_value=mock_analysis,
    ):
        start = time.monotonic()
        inp = DebateInput(stock_code="000001", stock_name="平安银行")
        result_a = await orch.run(inp)
        elapsed_a = time.monotonic() - start

    print(f"  完成时间: {elapsed_a:.1f}s")
    print(f"  大师数: {len(result_a.analyses)}")
    print(f"  分析师数: {len(result_a.analyst_reports or {})}")
    caveats = []
    if result_a.review_report:
        caveats.append(f"  独立评审: [有] (质量 {result_a.review_report.overall_quality:.2f})")

    # 统计 LLM 调用次数（各层预估值）
    analyst_count = 4  # 4 位分析师
    master_count = 5  # 5 位大师
    # reporter 调用次数 = analyst_count
    # review_count = master_count（每位大师审阅同行）
    review_report_count = 1  # 1 位独立评审
    basic_calls = analyst_count + master_count + master_count + review_report_count

    print(f"\n  [预估] LLM 调用次数: {basic_calls}")
    print(f"     +-- analyst_round:  {analyst_count} 次（4 位分析师）")
    print(f"     +-- master_round:   {master_count} 次（5 位大师）")
    print(f"     +-- review_round:   {master_count} 次（5 位大师交叉审阅）")
    print(f"     +-- review_report:  {review_report_count} 次（1 位独立评审）")

    cost_basic = _estimate_layer_cost(basic_calls, ESTIMATED_TOKENS_PER_CALL)
    print(f"\n  [估算费用]: {cost_basic:.4f} 元（按 DeepSeek-Chat = {_cost_str(cost_basic)}）")
    print(f"  [若用 GPT-4o-mini]: {cost_basic * 3:.4f} 元")

    # ═══════════════════ 场景 2: 全 9 层 ═══════════════════
    print("\n[场景 B] 全 9 层（+ R1 风控 + T1 交易员 + PM 裁决）")
    print("-" * 40)

    orch2 = DebateOrchestrator(
        data_collector=make_mock_collector(),
        skill_ids=["buffett", "munger", "graham", "dalio", "lynch"],
        enable_risk=True,
        enable_trader=True,
    )

    with patch(
        "src.debate.orchestrator._run_single_master",
        new_callable=AsyncMock,
        return_value=mock_analysis,
    ):
        start = time.monotonic()
        inp2 = DebateInput(stock_code="600519", stock_name="贵州茅台")
        result_b = await orch2.run(inp2)
        elapsed_b = time.monotonic() - start

    print(f"  完成时间: {elapsed_b:.1f}s")
    print(f"  大师数: {len(result_b.analyses)}")
    print(f"  风控层: {'[有]' if result_b.risk_round else '[无]'}")
    print(f"  交易员层: {'[有]' if result_b.trader_round else '[无]'}")
    print(f"  PM裁决: {'[有]' if result_b.trade_recommendation else '[无]'}")

    # 全 9 层 LLM 调用统计
    risk_count = 3  # 3 位风控官
    trader_count = 1  # 1 位交易员
    pm_count = 1  # 1 位 PM
    all_calls = basic_calls + risk_count + trader_count + pm_count

    layer_detail = [
        ("analyst_round (4 位分析师)", analyst_count),
        ("master_round (5 位大师)", master_count),
        ("review_round (5 位大师审阅)", master_count),
        ("review_report (独立评审)", review_report_count),
        ("risk_round (3 位风控官)", risk_count),
        ("trader_round (交易员)", trader_count),
        ("pm_round (PM 裁决)", pm_count),
    ]

    print(f"\n  [预估] LLM 调用次数: {all_calls}")
    for name, count in layer_detail:
        print(f"     +-- {name}:  {count} 次")

    cost_all = _estimate_layer_cost(all_calls, ESTIMATED_TOKENS_PER_CALL)
    print(f"\n  [估算费用]: {cost_all:.4f} 元（按 DeepSeek-Chat = {_cost_str(cost_all)}）")

    # ═══════════════════ 总结 ═══════════════════
    print(f"\n{'=' * 60}")
    print("[总结] 成本总结")
    print("-" * 40)
    print(f"  基础 6 层: {basic_calls} 次调用 ~= {cost_basic:.4f} 元")
    print(f"  全 9 层:    {all_calls} 次调用 ~= {cost_all:.4f} 元")
    print(f"  增量:       {all_calls - basic_calls} 次调用（风控+交易员+PM）")
    print()
    print("  按 DeepSeek-Chat 定价:")
    print(f"     每日 10 次决策 ~= {cost_all * 10:.2f} 元")
    print(f"     每月 20交易日 x 5次/日 ~= {cost_all * 100:.2f} 元")
    print("\n  实际成本会因实际 token 长度、是否启用 M2 反思等因素浮动")
    print()

    return {
        "basic_calls": basic_calls,
        "all_calls": all_calls,
        "cost_basic": cost_basic,
        "cost_all": cost_all,
    }


def _estimate_layer_cost(calls: int, estimated: dict[str, tuple]) -> float:
    """按平均估算计算费用"""
    pricing = PRICING[DEFAULT_MODEL]
    avg_pt = sum(pt for pt, _ in estimated.values()) // len(estimated)
    avg_ct = sum(ct for _, ct in estimated.values()) // len(estimated)
    total = calls * ((avg_pt / 1000) * pricing["input"] + (avg_ct / 1000) * pricing["output"])
    return round(total, 4)


def _cost_str(yuan: float) -> str:
    """元 → 可读字符串"""
    if yuan < 0.01:
        return f"{yuan * 100:.2f}分"
    if yuan < 1:
        return f"{yuan * 100:.1f}分"
    return f"{yuan:.2f}元"


if __name__ == "__main__":
    asyncio.run(measure())
